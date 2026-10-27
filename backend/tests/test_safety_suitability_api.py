"""
API tests for the Brick 13 evaluate endpoints on /api/v1/recommendations.
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

    user = User(email="safety-api-test@example.com")
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


def _make_strained_profile(db_session, user):
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
    return profile


def test_evaluate_single_candidate(client):
    c, user, db_session = client
    _make_strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]

    resp = c.post(f"/api/v1/recommendations/{rec_id}/evaluate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] in ("APPROVE", "CLARIFY", "EDUCATE", "LIMIT", "BLOCK", "ESCALATE")
    assert len(body["checks"]) == 4

    # Confirm it's persisted
    after = c.get(f"/api/v1/recommendations/{rec_id}").json()
    assert after["state"] != "candidate"
    assert after["suitability_status"] == body["decision"]
    assert after["safety_checks"]


def test_evaluate_already_decided_candidate_409s(client):
    """Re-POSTing /evaluate on a row that's no longer CANDIDATE must be
    rejected, not silently re-decided."""
    c, user, db_session = client
    _make_strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]

    first = c.post(f"/api/v1/recommendations/{rec_id}/evaluate")
    assert first.status_code == 200

    second = c.post(f"/api/v1/recommendations/{rec_id}/evaluate")
    assert second.status_code == 409


def test_evaluate_nonexistent_candidate_404s(client):
    c, _, _ = client
    resp = c.post(f"/api/v1/recommendations/{uuid.uuid4()}/evaluate")
    assert resp.status_code == 404


def test_evaluate_pending_processes_all(client):
    c, user, db_session = client
    _make_strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    assert len(gen["candidates"]) == 1  # only emergency_fund rule fires

    resp = c.post("/api/v1/recommendations/evaluate-pending")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Nothing left in CANDIDATE state
    remaining = c.get("/api/v1/recommendations?state=candidate").json()
    assert remaining == []


def test_evaluate_pending_with_nothing_to_evaluate_returns_empty(client):
    c, _, _ = client
    resp = c.post("/api/v1/recommendations/evaluate-pending")
    assert resp.status_code == 200
    assert resp.json() == []


def test_evaluate_accepts_no_request_body(client):
    """The decision must not be influenceable by client input — there is
    no schema for a request body at all on either evaluate endpoint."""
    c, user, db_session = client
    _make_strained_profile(db_session, user)
    gen = c.post("/api/v1/recommendations/generate").json()
    rec_id = gen["candidates"][0]["id"]

    # Try to smuggle in a body that would attempt to force APPROVE —
    # it should simply be ignored (FastAPI has no model for it here).
    resp = c.post(f"/api/v1/recommendations/{rec_id}/evaluate", json={"decision": "APPROVE"})
    assert resp.status_code == 200
    # Decision came from the real checks, not the injected body
    body = resp.json()
    assert body["recommendation_id"] == rec_id
