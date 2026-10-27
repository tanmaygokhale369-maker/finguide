"""
Tests confirming financial-data extraction runs automatically when a
chat message is sent, is retrievable per-conversation, respects the same
ownership isolation as everything else, and never touches
FinancialProfile.
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

    user = User(email="extraction-test-user@example.com")
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


def _switch_current_user(db_session, email: str) -> TestClient:
    from app.core.user_context import get_current_user

    user = User(email=email)
    db_session.add(user)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_sending_a_message_with_financial_content_creates_extractions(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "I earn 60,000 a month, spend around 25,000 and have a 5 lakh loan."},
    )
    conversation_id = response.json()["conversation_id"]

    extractions = client.get(f"/api/v1/chat/{conversation_id}/extractions")
    assert extractions.status_code == 200
    body = extractions.json()

    by_field = {row["field_name"]: row for row in body}
    assert Decimal(by_field["monthly_income"]["value"]) == Decimal("60000")
    assert Decimal(by_field["monthly_expenses"]["value"]) == Decimal("25000")
    assert Decimal(by_field["debt"]["value"]) == Decimal("500000")
    for row in body:
        assert row["extraction_method"] == "regex_v1"
        assert row["message_id"]
        assert row["source_text"]


def test_message_with_no_financial_content_creates_no_extractions(client):
    response = client.post("/api/v1/chat", json={"message": "hello there"})
    conversation_id = response.json()["conversation_id"]

    extractions = client.get(f"/api/v1/chat/{conversation_id}/extractions")
    assert extractions.status_code == 200
    assert extractions.json() == []


def test_extractions_endpoint_returns_404_for_unknown_conversation(client):
    import uuid

    response = client.get(f"/api/v1/chat/{uuid.uuid4()}/extractions")
    assert response.status_code == 404


def test_cannot_view_another_users_extractions(client, db_session):
    mine = client.post("/api/v1/chat", json={"message": "I earn 70000 a month."})
    conversation_id = mine.json()["conversation_id"]

    other_client = _switch_current_user(db_session, "other-extraction-user@example.com")
    response = other_client.get(f"/api/v1/chat/{conversation_id}/extractions")
    assert response.status_code == 404


def test_extraction_never_creates_or_modifies_a_financial_profile(client):
    """
    Core architectural rule: extraction produces candidates only.
    Nothing about sending a chat message should create or touch
    FinancialProfile — that requires an explicit profile API call.
    """
    client.post(
        "/api/v1/chat",
        json={"message": "I earn 60,000 a month, spend around 25,000 and have a 5 lakh loan."},
    )

    profile_response = client.get("/api/v1/profile")
    assert profile_response.status_code == 404  # still no profile exists


def test_conflicting_values_in_one_message_both_appear_in_extractions(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "My income was 50000 last year but now I earn 80000."},
    )
    conversation_id = response.json()["conversation_id"]

    extractions = client.get(f"/api/v1/chat/{conversation_id}/extractions")
    values = {Decimal(row["value"]) for row in extractions.json() if row["field_name"] == "monthly_income"}
    assert values == {Decimal("50000"), Decimal("80000")}


def test_ambiguity_flag_and_reason_are_exposed_through_the_api(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "My income was 50000 last year but now I earn 80000."},
    )
    conversation_id = response.json()["conversation_id"]

    extractions = client.get(f"/api/v1/chat/{conversation_id}/extractions").json()
    income_rows = [row for row in extractions if row["field_name"] == "monthly_income"]
    assert len(income_rows) == 2
    for row in income_rows:
        assert row["is_ambiguous"] is True
        assert row["ambiguity_reason"]


def test_unambiguous_extraction_has_flag_false_and_no_reason(client):
    response = client.post("/api/v1/chat", json={"message": "I earn 50000 monthly."})
    conversation_id = response.json()["conversation_id"]

    extractions = client.get(f"/api/v1/chat/{conversation_id}/extractions").json()
    income_row = next(row for row in extractions if row["field_name"] == "monthly_income")
    assert income_row["is_ambiguous"] is False
    assert income_row["ambiguity_reason"] is None
