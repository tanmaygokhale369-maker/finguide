"""
Tests for the transaction API.

Follows the same fresh-user-per-test dependency-override pattern as
test_profile_api.py / test_chat_api.py, and the same sequential-identity-
switch helper as test_chat_api.py for isolation tests (two simultaneous
client fixtures both mutating the global app.dependency_overrides dict
would silently clobber each other — see that file's history).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="txn-test-user@example.com")
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


def _create(client, **overrides):
    payload = {
        "amount": "1500.50",
        "type": "expense",
        "category": "groceries",
        "transaction_date": str(date.today()),
        "description": "Weekly shop",
    }
    payload.update(overrides)
    return client.post("/api/v1/transactions", json=payload)


def test_create_transaction(client):
    response = _create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "1500.50"
    assert body["category"] == "groceries"
    assert body["source"] == "manual"
    assert body["confidence"] is None


def test_source_and_confidence_are_not_client_settable(client):
    """Provenance fields must be server-controlled, not client input."""
    response = _create(client, source="bank_import", confidence="0.99")
    assert response.status_code == 422  # extra="forbid" on the schema


def test_negative_amount_is_rejected(client):
    response = _create(client, amount="-10")
    assert response.status_code == 422


def test_zero_amount_is_rejected(client):
    response = _create(client, amount="0")
    assert response.status_code == 422


def test_invalid_category_is_rejected(client):
    response = _create(client, category="not_a_real_category")
    assert response.status_code == 422


def test_future_date_is_rejected(client):
    tomorrow = str(date.today() + timedelta(days=1))
    response = _create(client, transaction_date=tomorrow)
    assert response.status_code == 422


def test_monetary_precision_is_preserved_exactly(client):
    response = _create(client, amount="1234.56")
    body = response.json()
    assert body["amount"] == "1234.56"
    assert Decimal(body["amount"]) == Decimal("1234.56")


def test_get_transaction_by_id(client):
    created = _create(client).json()
    response = client.get(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_transaction_returns_404(client):
    import uuid

    response = client.get(f"/api/v1/transactions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_transactions_returns_most_recent_first(client):
    _create(client, transaction_date=str(date.today() - timedelta(days=5)), description="older")
    _create(client, transaction_date=str(date.today()), description="newer")

    response = client.get("/api/v1/transactions")
    body = response.json()
    assert len(body) == 2
    assert body[0]["description"] == "newer"
    assert body[1]["description"] == "older"


def test_list_filters_by_type(client):
    _create(client, type="expense", category="groceries")
    _create(client, type="income", category="salary")

    response = client.get("/api/v1/transactions", params={"type": "income"})
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "income"


def test_list_filters_by_category(client):
    _create(client, category="groceries")
    _create(client, category="entertainment")

    response = client.get("/api/v1/transactions", params={"category": "entertainment"})
    body = response.json()
    assert len(body) == 1
    assert body[0]["category"] == "entertainment"


def test_list_filters_by_date_range(client):
    _create(client, transaction_date=str(date.today() - timedelta(days=10)))
    _create(client, transaction_date=str(date.today()))

    response = client.get(
        "/api/v1/transactions",
        params={"start_date": str(date.today() - timedelta(days=1))},
    )
    body = response.json()
    assert len(body) == 1


def test_list_respects_limit(client):
    for _ in range(5):
        _create(client)

    response = client.get("/api/v1/transactions", params={"limit": 2})
    assert len(response.json()) == 2


def test_update_changes_only_provided_fields(client):
    created = _create(client, amount="1000.00", category="groceries").json()

    response = client.patch(f"/api/v1/transactions/{created['id']}", json={"amount": "2000.00"})
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "2000.00"
    assert body["category"] == "groceries"  # untouched


def test_update_can_clear_description_to_null(client):
    created = _create(client, description="something").json()

    response = client.patch(f"/api/v1/transactions/{created['id']}", json={"description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_update_cannot_set_required_field_to_null(client):
    created = _create(client).json()

    response = client.patch(f"/api/v1/transactions/{created['id']}", json={"amount": None})
    assert response.status_code == 422


def test_update_unknown_transaction_returns_404(client):
    import uuid

    response = client.patch(f"/api/v1/transactions/{uuid.uuid4()}", json={"amount": "1.00"})
    assert response.status_code == 404


def test_delete_transaction(client):
    created = _create(client).json()

    delete_response = client.delete(f"/api/v1/transactions/{created['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/transactions/{created['id']}")
    assert get_response.status_code == 404


def test_delete_unknown_transaction_returns_404(client):
    import uuid

    response = client.delete(f"/api/v1/transactions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_cannot_get_another_users_transaction(client, db_session):
    created = _create(client).json()

    other_client = _switch_current_user(db_session, "other-txn-user@example.com")
    response = other_client.get(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 404


def test_cannot_update_another_users_transaction(client, db_session):
    created = _create(client).json()

    other_client = _switch_current_user(db_session, "other-txn-user-2@example.com")
    response = other_client.patch(f"/api/v1/transactions/{created['id']}", json={"amount": "1.00"})
    assert response.status_code == 404


def test_cannot_delete_another_users_transaction(client, db_session):
    created = _create(client).json()

    other_client = _switch_current_user(db_session, "other-txn-user-3@example.com")
    response = other_client.delete(f"/api/v1/transactions/{created['id']}")
    assert response.status_code == 404


def test_list_is_isolated_per_user(client, db_session):
    _create(client)

    other_client = _switch_current_user(db_session, "other-txn-user-4@example.com")
    response = other_client.get("/api/v1/transactions")
    assert response.json() == []
