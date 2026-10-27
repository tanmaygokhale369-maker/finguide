"""
Unit tests for app/services/safety_suitability_service.py (Brick 13).
"""

import uuid
from decimal import Decimal

import pytest

from app.models.financial_profile import FinancialProfile
from app.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationRiskLevel,
    RecommendationState,
)
from app.models.user import User
from app.services import metrics_service, recommendation_service, safety_suitability_service as service


@pytest.fixture()
def user(db_session):
    u = User(email="safety-test@example.com")
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
        emergency_fund_amount=Decimal("30000"),  # 1 month -> triggers emergency_fund rule
    )
    defaults.update(overrides)
    p = FinancialProfile(**defaults)
    db_session.add(p)
    db_session.flush()
    return p


def _bare_candidate(db_session, user, **overrides):
    """A hand-built CANDIDATE row for testing checks in isolation,
    bypassing recommendation_service entirely."""
    defaults = dict(
        user_id=user.id,
        category=RecommendationCategory.SAVINGS,
        title="Increase your savings rate",
        reason="You're saving about 5.0% of your income.",
        confidence=Decimal("1.00"),
        risk_level=RecommendationRiskLevel.LOW,
        state=RecommendationState.CANDIDATE,
        suitability_status=None,
        source_references=[],
        based_on={"computation_id": str(uuid.uuid4())},  # deliberately bogus -> stale by default
        rule_id="low_savings_ratio",
        policy_version=service.CURRENT_POLICY_VERSION,
    )
    defaults.update(overrides)
    rec = Recommendation(**defaults)
    db_session.add(rec)
    db_session.flush()
    return rec


def test_emergency_fund_candidate_approved_end_to_end(db_session, user):
    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "emergency_fund_low_coverage")

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "APPROVE"
    assert result.state == RecommendationState.APPROVED
    assert candidate.state == RecommendationState.APPROVED
    assert candidate.suitability_status == "APPROVE"
    assert candidate.safety_explanation
    assert len(candidate.safety_checks) == 4
    assert all(c["passed"] for c in candidate.safety_checks)


def test_budgeting_candidate_mapped_to_educate(db_session, user):
    profile = _profile(
        db_session,
        user,
        fixed_expenses=Decimal("30000"),
        variable_expenses=Decimal("27000"),  # 95% expense ratio -> high_expense_to_income_ratio rule
    )
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "high_expense_to_income_ratio")

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "EDUCATE"
    # EDUCATE has no matching lifecycle value -> maps to MODIFIED (see module docstring)
    assert result.state == RecommendationState.MODIFIED
    assert candidate.suitability_status == "EDUCATE"
    assert candidate.state == RecommendationState.MODIFIED


def test_debt_candidate_requires_clarify(db_session, user):
    profile = _profile(db_session, user, debt=Decimal("500000"))  # triggers high_debt_to_income_ratio
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "high_debt_to_income_ratio")

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "CLARIFY"
    assert result.state == RecommendationState.CLARIFY
    assert "repayment" in candidate.safety_explanation.lower()


def test_stale_candidate_is_blocked(db_session, user):
    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    # based_on.computation_id is a random uuid, not the real latest one -> stale
    candidate = _bare_candidate(db_session, user)

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "BLOCK"
    assert result.state == RecommendationState.BLOCKED
    assert "recomputed" in candidate.safety_explanation.lower() or "stale" in candidate.safety_explanation.lower()


def test_policy_version_mismatch_escalates(db_session, user):
    profile = _profile(db_session, user)
    computation_id, _ = metrics_service.compute_and_store_metrics(db_session, profile)
    candidate = _bare_candidate(
        db_session,
        user,
        based_on={"computation_id": str(computation_id)},
        policy_version="v999",
    )

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "ESCALATE"
    assert result.state == RecommendationState.ESCALATE


def test_forbidden_language_blocks_even_with_fresh_data(db_session, user):
    profile = _profile(db_session, user)
    computation_id, _ = metrics_service.compute_and_store_metrics(db_session, profile)
    candidate = _bare_candidate(
        db_session,
        user,
        based_on={"computation_id": str(computation_id)},
        reason="This is a guaranteed way to grow your savings with no risk.",
    )

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "BLOCK"
    forbidden_check = next(c for c in result.checks if c.check == "forbidden_language")
    assert forbidden_check.passed is False


def test_high_risk_escalates_regardless_of_category(db_session, user):
    profile = _profile(db_session, user)
    computation_id, _ = metrics_service.compute_and_store_metrics(db_session, profile)
    candidate = _bare_candidate(
        db_session,
        user,
        based_on={"computation_id": str(computation_id)},
        category=RecommendationCategory.SAVINGS,
        risk_level=RecommendationRiskLevel.HIGH,
    )

    result = service.evaluate_candidate(db_session, candidate)

    assert result.decision == "ESCALATE"


def test_evaluate_pending_candidates_processes_all_open_ones(db_session, user):
    profile = _profile(db_session, user, debt=Decimal("500000"))  # 2 rules fire: emergency_fund + debt
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    assert len(gen.candidates) == 2

    results = service.evaluate_pending_candidates(db_session, user.id)

    assert len(results) == 2
    remaining_candidates = recommendation_service.list_recommendations(
        db_session, user.id, state=RecommendationState.CANDIDATE
    )
    assert remaining_candidates == []  # none left in CANDIDATE state


def test_evaluation_is_isolated_per_user(db_session, user):
    other = User(email="safety-test-other@example.com")
    db_session.add(other)
    db_session.flush()

    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    recommendation_service.generate_candidates(db_session, user.id)

    # other user has no candidates at all -> nothing to evaluate, no crash
    results = service.evaluate_pending_candidates(db_session, other.id)
    assert results == []


def test_get_recommendation_not_found_raises(db_session, user):
    with pytest.raises(service.RecommendationNotFoundError):
        service.get_recommendation(db_session, user.id, uuid.uuid4())
