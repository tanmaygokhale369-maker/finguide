"""
Tests for the validation API — going through the real chat pipeline
(POST /api/v1/chat), not calling revalidate_field directly, to confirm
extraction_service actually wires validation in (it's easy to add a
validation_service without ever calling it — see the module docstring
history in extraction_service.py).
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="validation-api-test@example.com")
    db_session.add(user)
    db_session.flush()

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_all_fields_start_incomplete(client):
    response = client.get("/api/v1/validation/fields")
    assert response.status_code == 200
    body = response.json()
    assert {row["field_name"] for row in body} == {
        "monthly_income",
        "monthly_expenses",
        "debt",
        "savings",
        "dependents",
    }
    assert all(row["status"] == "INCOMPLETE" for row in body)


def test_sending_a_clear_message_produces_a_valid_field(client):
    client.post("/api/v1/chat", json={"message": "I earn 60000 monthly."})

    response = client.get("/api/v1/validation/fields/monthly_income")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "VALID"
    assert body["value"] == "60000.0000"


def test_conflicting_messages_require_clarification_via_the_real_pipeline(client):
    """
    This is the doc's own literal example, sent as two separate chat
    messages (not one sentence) — confirming extraction_service actually
    calls revalidate_field, end to end through the real API.
    """
    client.post("/api/v1/chat", json={"message": "My income is 50000."})
    client.post("/api/v1/chat", json={"message": "Actually my income is 80000."})

    response = client.get("/api/v1/validation/fields/monthly_income")
    body = response.json()
    assert body["status"] == "REQUIRES_CLARIFICATION"
    assert body["value"] is None
    assert len(body["contributing_field_ids"]) == 2


def test_unknown_field_name_returns_404(client):
    response = client.get("/api/v1/validation/fields/not_a_real_field")
    assert response.status_code == 404


def test_validation_never_creates_or_touches_a_financial_profile(client):
    """
    Structural regression guard for the architecture rule that extracted/
    validated data never automatically becomes profile data — only the
    explicit profile API (Brick 05) can create or modify a profile.
    """
    client.post(
        "/api/v1/chat",
        json={"message": "I earn 60000 monthly, spend 25000, and have 500000 in debt."},
    )
    client.get("/api/v1/validation/fields")

    profile_response = client.get("/api/v1/profile")
    assert profile_response.status_code == 404  # still doesn't exist


def test_validation_is_isolated_per_user(client, db_session):
    client.post("/api/v1/chat", json={"message": "I earn 60000 monthly."})

    from app.core.user_context import get_current_user

    other_user = User(email="validation-other-user@example.com")
    db_session.add(other_user)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: other_user
    other_client = TestClient(app)

    response = other_client.get("/api/v1/validation/fields/monthly_income")
    assert response.json()["status"] == "INCOMPLETE"
