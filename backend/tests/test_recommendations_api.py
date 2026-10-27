"""
API tests for /api/v1/recommendations (Brick 12).
"""

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

    user = User(email="rec-api-test@example.com")
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


def test_generate_without_profile_returns_no_metrics_computed(client):
    c, _, _ = client
    resp = c.post("/api/v1/recommendations/generate")
    assert resp.status_code == 201
    body = resp.json()
    assert body["context_status"] == "NO_METRICS_COMPUTED"
    assert body["candidates"] == []


def test_generate_with_strained_profile_returns_candidates(client):
    c, user, db_session = client
    profile = FinancialProfile(
        user_id=user.id,
        monthly_income=Decimal("60000"),
        fixed_expenses=Decimal("20000"),
        variable_expenses=Decimal("10000"),
        emergency_fund_amount=Decimal("30000"),  # 1 month -> low
    )
    db_session.add(profile)
    db_session.flush()
    metrics_service.compute_and_store_metrics(db_session, profile)

    resp = c.post("/api/v1/recommendations/generate")
    assert resp.status_code == 201
    body = resp.json()
    assert body["context_status"] == "OK"
    assert len(body["candidates"]) >= 1
    for cand in body["candidates"]:
        assert cand["state"] == "candidate"
        assert cand["suitability_status"] is None
        assert cand["source_references"] == []


def test_list_recommendations_after_generate(client):
    c, user, db_session = client
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
    c.post("/api/v1/recommendations/generate")

    resp = c.get("/api/v1/recommendations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_single_recommendation(client):
    c, user, db_session = client
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
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]

    resp = c.get(f"/api/v1/recommendations/{rec_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rec_id


def test_get_nonexistent_recommendation_404s(client):
    import uuid

    c, _, _ = client
    resp = c.get(f"/api/v1/recommendations/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_isolated_per_user(client):
    c, user, db_session = client
    other = User(email="rec-api-other@example.com")
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

    recommendation_service.generate_candidates(db_session, other.id)

    resp = c.get("/api/v1/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_no_write_endpoints_besides_generate(client):
    """Recommendations are never client-edited — only /generate writes."""
    c, _, _ = client
    import uuid

    resp = c.patch(f"/api/v1/recommendations/{uuid.uuid4()}", json={})
    assert resp.status_code in (404, 405)
    resp = c.delete(f"/api/v1/recommendations/{uuid.uuid4()}")
    assert resp.status_code in (404, 405)
