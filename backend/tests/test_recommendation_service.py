"""
Unit tests for app/services/recommendation_service.py (Brick 12).
"""

from decimal import Decimal

import pytest

from app.models.financial_profile import FinancialProfile
from app.models.recommendation import Recommendation, RecommendationState
from app.models.user import User
from app.services import metrics_service, recommendation_service as service


@pytest.fixture()
def user(db_session):
    u = User(email="rec-test@example.com")
    db_session.add(u)
    db_session.flush()
    return u


def _profile(db_session, user, **overrides):
    defaults = dict(
        user_id=user.id,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("20000"),
        variable_expenses=Decimal("10000"),
        savings=Decimal("5000"),
        debt=Decimal("0"),
        emergency_fund_amount=Decimal("90000"),  # 3 months of expenses -> not low
    )
    defaults.update(overrides)
    p = FinancialProfile(**defaults)
    db_session.add(p)
    db_session.flush()
    return p


def test_no_metrics_computed_yet_returns_explicit_context_status(db_session, user):
    _profile(db_session, user)  # profile exists but metrics never computed
    result = service.generate_candidates(db_session, user.id)
    assert result.context_status == "NO_METRICS_COMPUTED"
    assert result.candidates == []


def test_healthy_profile_produces_no_candidates(db_session, user):
    profile = _profile(db_session, user)  # comfortable on every metric
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    assert result.context_status == "OK"
    assert result.candidates == []
    # every rule should have been evaluated and explicitly skipped as "not met"
    reasons = {s.reason for s in result.skipped}
    assert reasons == {"threshold_not_met"}
    assert len(result.skipped) == 4


def test_low_emergency_fund_triggers_candidate(db_session, user):
    # 1 month of expenses covered (expenses = 30000/mo, fund = 30000)
    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    rule_ids = {c.rule_id for c in result.candidates}
    assert "emergency_fund_low_coverage" in rule_ids
    candidate = next(c for c in result.candidates if c.rule_id == "emergency_fund_low_coverage")
    assert candidate.state == RecommendationState.CANDIDATE
    assert candidate.suitability_status is None
    assert candidate.source_references == []
    assert candidate.based_on["metric_name"] == "emergency_fund_coverage_months"
    assert candidate.category.value == "emergency_fund"


def test_high_expense_ratio_triggers_candidate(db_session, user):
    # expenses (28000+28000=... ) -> make expenses 95% of income
    profile = _profile(
        db_session,
        user,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("30000"),
        variable_expenses=Decimal("27000"),  # total 57000 / 60000 = 0.95
    )
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    rule_ids = {c.rule_id for c in result.candidates}
    assert "high_expense_to_income_ratio" in rule_ids


def test_low_savings_ratio_triggers_candidate(db_session, user):
    # savings_ratio = (income - fixed - variable) / income; make it < 10%
    profile = _profile(
        db_session,
        user,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("30000"),
        variable_expenses=Decimal("27000"),  # net 3000 / 60000 = 5%
    )
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    rule_ids = {c.rule_id for c in result.candidates}
    assert "low_savings_ratio" in rule_ids


def test_high_debt_to_income_triggers_candidate(db_session, user):
    profile = _profile(db_session, user, debt=Decimal("500000"), monthly_income=Decimal("60000"))  # ~8.3 months
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    rule_ids = {c.rule_id for c in result.candidates}
    assert "high_debt_to_income_ratio" in rule_ids


def test_incomplete_metric_is_skipped_not_silently_assumed(db_session, user):
    # No debt field set at all -> debt_to_income_ratio is INCOMPLETE, not "0 debt"
    profile = _profile(db_session, user, debt=None)
    metrics_service.compute_and_store_metrics(db_session, profile)

    result = service.generate_candidates(db_session, user.id)

    skip_reasons = {s.rule_id: s.reason for s in result.skipped}
    assert skip_reasons["high_debt_to_income_ratio"] == "metric_incomplete"


def test_regenerating_does_not_duplicate_open_candidates(db_session, user):
    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    metrics_service.compute_and_store_metrics(db_session, profile)

    result1 = service.generate_candidates(db_session, user.id)
    result2 = service.generate_candidates(db_session, user.id)

    ids1 = {c.id for c in result1.candidates}
    ids2 = {c.id for c in result2.candidates}
    assert ids1 == ids2  # same row reused, not duplicated

    count = (
        db_session.query(Recommendation)
        .filter(Recommendation.user_id == user.id, Recommendation.rule_id == "emergency_fund_low_coverage")
        .count()
    )
    assert count == 1


def test_regenerating_after_evaluation_same_computation_does_not_duplicate(db_session, user):
    """
    Caught by live smoke testing: once Brick 13 evaluates a candidate
    (moving it out of CANDIDATE state), calling generate_candidates
    again against the SAME unchanged computation must still return the
    existing (now-decided) row, not create a duplicate for a condition
    that was already decided.
    """
    from app.services import safety_suitability_service

    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    metrics_service.compute_and_store_metrics(db_session, profile)

    result1 = service.generate_candidates(db_session, user.id)
    candidate = next(c for c in result1.candidates if c.rule_id == "emergency_fund_low_coverage")
    safety_suitability_service.evaluate_candidate(db_session, candidate)
    assert candidate.state == RecommendationState.APPROVED

    # Nothing about the profile/metrics changed -> regenerate should
    # return the SAME (now-APPROVED) row, not create a new CANDIDATE one.
    result2 = service.generate_candidates(db_session, user.id)
    same = next(c for c in result2.candidates if c.rule_id == "emergency_fund_low_coverage")
    assert same.id == candidate.id
    assert same.state == RecommendationState.APPROVED

    count = (
        db_session.query(Recommendation)
        .filter(Recommendation.user_id == user.id, Recommendation.rule_id == "emergency_fund_low_coverage")
        .count()
    )
    assert count == 1


def test_regenerating_after_recompute_produces_fresh_candidate_not_stale_reuse(db_session, user):
    """
    Caught by live smoke testing, not by the original test suite: the
    idempotency check must key on (rule_id, computation_id), not rule_id
    alone — otherwise a candidate generated before a profile update stays
    open forever and a fresh computation never produces a fresh
    candidate, only an endlessly-reused stale one.
    """
    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    computation_id_1, _ = metrics_service.compute_and_store_metrics(db_session, profile)
    result1 = service.generate_candidates(db_session, user.id)
    old_candidate = next(c for c in result1.candidates if c.rule_id == "emergency_fund_low_coverage")
    assert old_candidate.based_on["computation_id"] == str(computation_id_1)

    # Profile changes, metrics recomputed -> new computation_id, rule still fires
    profile.emergency_fund_amount = Decimal("15000")
    db_session.flush()
    computation_id_2, _ = metrics_service.compute_and_store_metrics(db_session, profile)
    assert computation_id_2 != computation_id_1

    result2 = service.generate_candidates(db_session, user.id)
    new_candidate = next(c for c in result2.candidates if c.rule_id == "emergency_fund_low_coverage")

    # A fresh row was created, not the old stale one reused
    assert new_candidate.id != old_candidate.id
    assert new_candidate.based_on["computation_id"] == str(computation_id_2)

    # The old one is left behind, still CANDIDATE, still referencing the
    # old computation -> Brick 13's staleness check will correctly BLOCK
    # it if/when evaluated.
    still_open = (
        db_session.query(Recommendation)
        .filter(Recommendation.id == old_candidate.id)
        .first()
    )
    assert still_open.state == RecommendationState.CANDIDATE
    assert still_open.based_on["computation_id"] == str(computation_id_1)


def test_results_isolated_per_user(db_session, user):
    other = User(email="rec-test-other@example.com")
    db_session.add(other)
    db_session.flush()

    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    metrics_service.compute_and_store_metrics(db_session, profile)
    service.generate_candidates(db_session, user.id)

    other_result = service.generate_candidates(db_session, other.id)
    assert other_result.context_status == "NO_METRICS_COMPUTED"

    other_recs = service.list_recommendations(db_session, other.id)
    assert other_recs == []


def test_get_recommendation_not_found_raises(db_session, user):
    import uuid

    with pytest.raises(service.RecommendationNotFoundError):
        service.get_recommendation(db_session, user.id, uuid.uuid4())


def test_list_recommendations_filters_by_state(db_session, user):
    profile = _profile(db_session, user, emergency_fund_amount=Decimal("30000"))
    metrics_service.compute_and_store_metrics(db_session, profile)
    service.generate_candidates(db_session, user.id)

    candidates = service.list_recommendations(db_session, user.id, state=RecommendationState.CANDIDATE)
    assert len(candidates) == 1

    approved = service.list_recommendations(db_session, user.id, state=RecommendationState.APPROVED)
    assert approved == []
