from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.feedback import RecommendationAuditEvent, SafetyIncident
from app.models.recommendation import Recommendation, RecommendationCategory, RecommendationRiskLevel, RecommendationState
from app.models.user import User


@pytest.fixture
def client(db_session):
    def override_db():
        yield db_session

    user = db_session.query(User).filter(User.email == "brick15-20@example.com").first()
    if user is None:
        user = User(email="brick15-20@example.com", full_name="API Test User")
        db_session.add(user)
        db_session.flush()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _approved_recommendation(db_session, user_id):
    row = Recommendation(
        user_id=user_id,
        category=RecommendationCategory.SAVINGS,
        title="Build savings steadily",
        reason="Your computed savings ratio is below the rule threshold.",
        confidence=Decimal("1.00"),
        risk_level=RecommendationRiskLevel.LOW,
        state=RecommendationState.APPROVED,
        suitability_status="APPROVE",
        safety_explanation="All deterministic checks passed.",
        safety_checks=[],
        source_references=[],
        based_on={},
        rule_id="test_rule",
        policy_version="v1",
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_registration_requires_consent_and_sets_httponly_session(client):
    missing_consent = client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "a sufficiently long password", "financial_analysis_consent": False})
    assert missing_consent.status_code == 400
    response = client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "a sufficiently long password", "financial_analysis_consent": True})
    assert response.status_code == 201
    assert response.json()["authenticated"] is True
    assert response.cookies.get("finguide_session")
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "access_token" not in response.json()


def test_cookie_authentication_is_required_outside_development(db_session, monkeypatch):
    from app.core import user_context

    def override_db():
        yield db_session

    monkeypatch.setattr(user_context.settings, "environment", "test")
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            registered = test_client.post("/api/v1/auth/register", json={"email": "cookie-user@example.com", "password": "a sufficiently long password", "financial_analysis_consent": True})
            assert registered.status_code == 201
            # Authenticated account has no profile yet; 404 proves session resolution.
            assert test_client.get("/api/v1/profile").status_code == 404
            assert test_client.post("/api/v1/auth/logout").status_code == 204
            assert test_client.get("/api/v1/profile").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_production_consent_revocation_and_account_deletion(db_session, monkeypatch):
    from app.core import user_context

    def override_db():
        yield db_session

    monkeypatch.setattr(user_context.settings, "environment", "production")
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, base_url="https://testserver") as test_client:
            registered = test_client.post("/api/v1/auth/register", json={"email": "privacy-user@example.com", "password": "a sufficiently long password", "financial_analysis_consent": True})
            assert registered.status_code == 201
            assert test_client.get("/api/v1/profile").status_code == 404
            revoked = test_client.post("/api/v1/privacy/consent", json={"purpose": "financial_analysis", "granted": False, "policy_version": "v1"})
            assert revoked.status_code == 201
            assert test_client.get("/api/v1/profile").status_code == 403
            assert test_client.get("/api/v1/privacy/export").json()["account"]["email"] == "privacy-user@example.com"
            deleted = test_client.request("DELETE", "/api/v1/privacy/account", json={"password": "a sufficiently long password", "confirm": True})
            assert deleted.status_code == 204
            assert db_session.query(User).filter(User.email == "privacy-user@example.com").count() == 0
            assert test_client.get("/api/v1/profile").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_client_evidence_is_unverified_zero_credibility_and_hash_stable(client):
    retrieved = datetime.now(timezone.utc).isoformat()
    payload = {"source_name": "Client attachment", "source_type": "news", "source_url": "https://example.org/story", "retrieved_at": retrieved, "title": "A market headline", "content": "External text is untrusted."}
    first = client.post("/api/v1/evidence", json=payload)
    duplicate = client.post("/api/v1/evidence", json=payload)
    assert first.status_code == 200
    assert first.json()["verification_status"] == "unverified"
    assert first.json()["credibility"] == "0.00"
    assert first.json()["sentiment_label"] == "uncertain"
    assert first.json()["conflict_metadata"]["verification"].startswith("Client supplied")
    assert first.json()["content_hash"] == duplicate.json()["content_hash"]
    assert len(client.get("/api/v1/evidence").json()) == 1


def test_approved_recommendation_requires_presentation_before_feedback_and_harmful_feedback_creates_incident(client, db_session):
    user = db_session.query(User).filter(User.email == "brick15-20@example.com").one()
    row = _approved_recommendation(db_session, user.id)
    db_session.commit()
    premature = client.post(f"/api/v1/recommendations/{row.id}/feedback", json={"action": "accepted", "rating": "helpful"})
    assert premature.status_code == 409
    presented = client.post(f"/api/v1/recommendations/{row.id}/present")
    assert presented.status_code == 200
    feedback = client.post(f"/api/v1/recommendations/{row.id}/feedback", json={"action": "rejected", "rating": "harmful", "comment": "This was unsuitable."})
    assert feedback.status_code == 201
    assert feedback.json()["incident_created"] is True
    db_session.refresh(row)
    assert row.state == RecommendationState.EVALUATED
    assert db_session.query(SafetyIncident).filter_by(recommendation_id=row.id, status="open").count() == 1
    assert [e.to_state for e in db_session.query(RecommendationAuditEvent).filter_by(recommendation_id=row.id).order_by(RecommendationAuditEvent.created_at).all()][-2:] == ["rejected", "evaluated"]


def test_nonapproved_recommendation_cannot_be_presented(client, db_session):
    user = db_session.query(User).filter(User.email == "brick15-20@example.com").one()
    row = Recommendation(
        user_id=user.id, category=RecommendationCategory.SAVINGS, title="Pending", reason="Reason",
        confidence=Decimal("1.00"), risk_level=RecommendationRiskLevel.LOW, state=RecommendationState.CANDIDATE,
        suitability_status=None, source_references=[], based_on={}, rule_id="pending_rule", policy_version="v1",
    )
    db_session.add(row)
    db_session.commit()
    assert client.post(f"/api/v1/recommendations/{row.id}/present").status_code == 409
