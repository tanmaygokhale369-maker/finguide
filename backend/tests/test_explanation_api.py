"""
API tests for GET /api/v1/recommendations/{id}/explanation (Brick 14).
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.financial_profile import FinancialProfile
from app.models.user import User
from app.services import metrics_service


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="explain-api-test@example.com")
    db_session.add(user)
    db_session.flush()

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield TestClient(app), user, db_session
    finally:
        app.dependency_overrides.clear()


def _strained_profile(db_session, user):
    profile = FinancialProfile(
        user_id=user.id,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("20000"),
        variable_expenses=Decimal("10000"),
        emergency_fund_amount=Decimal("30000"),
    )
    db_session.add(profile)
    db_session.flush()
    metrics_service.compute_and_store_metrics(db_session, profile)
    return profile


def test_explanation_for_candidate(client):
    c, user, db_session = client
    _strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]

    resp = c.get(f"/api/v1/recommendations/{rec_id}/explanation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation_id"] == rec_id
    assert body["what"]
    assert body["why"]
    assert body["user_data_used"]["metric_name"]
    assert body["external_evidence"] == []
    assert body["confidence"] == "1.00"
    assert len(body["limitations"]) >= 1


def test_explanation_available_after_evaluation(client):
    c, user, db_session = client
    _strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]
    c.post(f"/api/v1/recommendations/{rec_id}/evaluate")

    resp = c.get(f"/api/v1/recommendations/{rec_id}/explanation")
    assert resp.status_code == 200
    body = resp.json()
    assert not any("not yet passed" in lim for lim in body["limitations"])


def test_explanation_nonexistent_404s(client):
    c, _, _ = client
    resp = c.get(f"/api/v1/recommendations/{uuid.uuid4()}/explanation")
    assert resp.status_code == 404


def test_explanation_isolated_per_user(client):
    c, user, db_session = client
    other = User(email="explain-api-other@example.com")
    db_session.add(other)
    db_session.flush()
    other_profile = FinancialProfile(
        user_id=other.id,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("20000"),
        variable_expenses=Decimal("10000"),
        emergency_fund_amount=Decimal("30000"),
    )
    db_session.add(other_profile)
    db_session.flush()
    metrics_service.compute_and_store_metrics(db_session, other_profile)
    from app.services import recommendation_service

    gen = recommendation_service.generate_candidates(db_session, other.id)
    other_rec_id = gen.candidates[0].id

    resp = c.get(f"/api/v1/recommendations/{other_rec_id}/explanation")
    assert resp.status_code == 404
