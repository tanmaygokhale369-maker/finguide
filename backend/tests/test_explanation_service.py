"""
Unit tests for app/services/explanation_service.py (Brick 14).
"""

import uuid
from decimal import Decimal

import pytest

from app.models.financial_profile import FinancialProfile
from app.models.recommendation import RecommendationState
from app.models.user import User
from app.services import (
    explanation_service as service,
    metrics_service,
    recommendation_service,
    safety_suitability_service,
)


@pytest.fixture()
def user(db_session):
    u = User(email="explain-test@example.com")
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
        emergency_fund_amount=Decimal("30000"),  # 1 month -> triggers rule
    )
    defaults.update(overrides)
    p = FinancialProfile(**defaults)
    db_session.add(p)
    db_session.flush()
    return p


def test_not_found_raises(db_session, user):
    with pytest.raises(service.RecommendationNotFoundError):
        service.build_explanation(db_session, user.id, uuid.uuid4())


def test_explanation_for_unevaluated_candidate(db_session, user):
    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "emergency_fund_low_coverage")

    explanation = service.build_explanation(db_session, user.id, candidate.id)

    assert explanation.what.startswith("Build up your emergency fund")
    assert "month" in explanation.why.lower()
    assert explanation.user_data_used is not None
    assert explanation.user_data_used.metric_name == "emergency_fund_coverage_months"
    assert explanation.user_data_used.formula
    assert explanation.user_data_used.input_values
    assert explanation.external_evidence == []
    assert any("3 months" in a for a in explanation.assumptions)
    assert explanation.confidence == "1.00"
    assert any("not yet passed" in lim for lim in explanation.limitations)


def test_explanation_after_approval_no_longer_says_unevaluated(db_session, user):
    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "emergency_fund_low_coverage")
    safety_suitability_service.evaluate_candidate(db_session, candidate)
    assert candidate.state == RecommendationState.APPROVED

    explanation = service.build_explanation(db_session, user.id, candidate.id)

    assert not any("not yet passed" in lim for lim in explanation.limitations)
    # All safety checks passed on this clean profile -> no failed-check limitations
    assert not any("Safety check" in lim for lim in explanation.limitations)


def test_debt_category_always_carries_repayment_limitation(db_session, user):
    profile = _profile(db_session, user, debt=Decimal("500000"))
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "high_debt_to_income_ratio")

    explanation = service.build_explanation(db_session, user.id, candidate.id)

    assert any("repayment" in lim.lower() or "emi" in lim.lower() for lim in explanation.limitations)
    assert any("balance-based" in a.lower() or "payment-based" in a.lower() for a in explanation.assumptions)


def test_blocked_candidate_surfaces_failed_check_as_limitation(db_session, user):
    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = next(c for c in gen.candidates if c.rule_id == "emergency_fund_low_coverage")

    # Force a staleness failure by corrupting based_on's computation_id
    candidate.based_on = {**candidate.based_on, "computation_id": str(uuid.uuid4())}
    db_session.flush()
    safety_suitability_service.evaluate_candidate(db_session, candidate)
    assert candidate.state == RecommendationState.BLOCKED

    explanation = service.build_explanation(db_session, user.id, candidate.id)

    assert any("staleness" in lim.lower() for lim in explanation.limitations)


def test_isolated_per_user(db_session, user):
    other = User(email="explain-test-other@example.com")
    db_session.add(other)
    db_session.flush()

    profile = _profile(db_session, user)
    metrics_service.compute_and_store_metrics(db_session, profile)
    gen = recommendation_service.generate_candidates(db_session, user.id)
    candidate = gen.candidates[0]

    with pytest.raises(service.RecommendationNotFoundError):
        service.build_explanation(db_session, other.id, candidate.id)
