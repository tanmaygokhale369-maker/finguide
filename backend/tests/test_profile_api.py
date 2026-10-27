"""
Tests for the financial profile API.

Each test gets its own throwaway user via a `get_current_user` dependency
override — this isolates tests from each other and from the shared
dev-user singleton (which is tested separately in test_user_context.py),
so profile create/get/patch tests don't leak state across each other.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User


@pytest.fixture()
def client(db_session):
    """A TestClient whose get_db and get_current_user are overridden to
    use the isolated, rolled-back db_session fixture and a fresh user."""
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="profile-test-user@example.com")
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


def test_get_profile_returns_404_when_none_exists(client):
    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "http_error"


def test_create_profile_with_partial_data(client):
    response = client.post("/api/v1/profile", json={"monthly_income": "65000.00", "dependents": 2})
    assert response.status_code == 201
    body = response.json()
    assert body["monthly_income"] == "65000.00"
    assert body["dependents"] == 2
    # Everything not provided stays null — never defaulted to 0.
    assert body["debt"] is None
    assert body["savings"] is None
    assert body["has_insurance"] is None


def test_create_profile_twice_returns_409(client):
    first = client.post("/api/v1/profile", json={})
    assert first.status_code == 201

    second = client.post("/api/v1/profile", json={})
    assert second.status_code == 409
    assert second.json()["error"]["type"] == "http_error"


def test_get_profile_after_create(client):
    client.post("/api/v1/profile", json={"monthly_income": "50000.00"})
    response = client.get("/api/v1/profile")
    assert response.status_code == 200
    assert response.json()["monthly_income"] == "50000.00"


def test_patch_updates_only_provided_fields(client):
    client.post("/api/v1/profile", json={"monthly_income": "50000.00", "debt": "10000.00"})

    response = client.patch("/api/v1/profile", json={"debt": "5000.00"})
    assert response.status_code == 200
    body = response.json()
    assert body["debt"] == "5000.00"
    # Untouched field is unchanged, not reset.
    assert body["monthly_income"] == "50000.00"


def test_patch_can_explicitly_clear_a_field_to_null(client):
    client.post("/api/v1/profile", json={"debt": "10000.00"})

    response = client.patch("/api/v1/profile", json={"debt": None})
    assert response.status_code == 200
    assert response.json()["debt"] is None


def test_patch_returns_404_when_no_profile_exists(client):
    response = client.patch("/api/v1/profile", json={"debt": "1000.00"})
    assert response.status_code == 404


def test_negative_income_is_rejected(client):
    response = client.post("/api/v1/profile", json={"monthly_income": "-100.00"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "validation_error"
    assert any(detail["field"].endswith("monthly_income") for detail in body["error"]["details"])


def test_unknown_field_is_rejected(client):
    response = client.post("/api/v1/profile", json={"not_a_real_field": 1})
    assert response.status_code == 422
