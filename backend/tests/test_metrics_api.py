from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="metrics-api-test@example.com")
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


def test_metrics_endpoint_404s_when_no_profile_exists(client):
    response = client.get("/api/v1/profile/metrics")
    assert response.status_code == 404


def test_metrics_computed_from_a_full_profile(client):
    client.post(
        "/api/v1/profile",
        json={
            "monthly_income": "50000",
            "fixed_expenses": "15000",
            "variable_expenses": "10000",
            "debt": "100000",
            "emergency_fund_amount": "30000",
        },
    )

    response = client.get("/api/v1/profile/metrics")
    assert response.status_code == 200
    body = response.json()
    by_name = {row["metric_name"]: row for row in body}
    assert by_name["expense_to_income_ratio"]["value"] == "0.500000"
    assert by_name["expense_to_income_ratio"]["status"] == "COMPUTED"
    assert by_name["debt_to_income_ratio"]["value"] == "2.000000"


def test_metrics_from_partial_profile_are_incomplete_with_reason(client):
    client.post("/api/v1/profile", json={"monthly_income": "50000"})

    response = client.get("/api/v1/profile/metrics")
    body = response.json()
    by_name = {row["metric_name"]: row for row in body}
    assert by_name["savings_ratio"]["status"] == "INCOMPLETE"
    assert by_name["savings_ratio"]["value"] is None
    assert "fixed_expenses" in by_name["savings_ratio"]["missing_inputs"]


def test_each_metrics_call_creates_a_new_history_entry(client):
    client.post("/api/v1/profile", json={"monthly_income": "50000", "fixed_expenses": "10000", "variable_expenses": "5000"})

    client.get("/api/v1/profile/metrics")
    client.get("/api/v1/profile/metrics")
    client.get("/api/v1/profile/metrics")

    history = client.get("/api/v1/profile/metrics/history").json()
    assert len(history) == 3


def test_history_entries_are_most_recent_first(client):
    client.post("/api/v1/profile", json={"monthly_income": "50000", "fixed_expenses": "10000", "variable_expenses": "5000"})
    first = client.get("/api/v1/profile/metrics").json()
    client.patch("/api/v1/profile", json={"fixed_expenses": "20000"})
    second = client.get("/api/v1/profile/metrics").json()

    history = client.get("/api/v1/profile/metrics/history").json()
    assert history[0]["computation_id"] == second[0]["computation_id"]
    assert history[1]["computation_id"] == first[0]["computation_id"]


def test_a_past_computation_is_retrievable_and_unchanged_by_later_edits(client):
    """
    This is the core 'reproducible' / 'versioning' guarantee: a past
    computation's stored values must reflect the profile as it was at
    that time, not the current profile.
    """
    client.post("/api/v1/profile", json={"monthly_income": "50000", "fixed_expenses": "10000", "variable_expenses": "5000"})
    first = client.get("/api/v1/profile/metrics").json()
    first_computation_id = first[0]["computation_id"]
    first_savings_ratio = next(r["value"] for r in first if r["metric_name"] == "savings_ratio")

    # Change the profile drastically and compute again.
    client.patch("/api/v1/profile", json={"fixed_expenses": "40000"})
    client.get("/api/v1/profile/metrics")

    # The OLD computation, fetched by id, must be unchanged.
    replay = client.get(f"/api/v1/profile/metrics/history/{first_computation_id}").json()
    replay_savings_ratio = next(r["value"] for r in replay if r["metric_name"] == "savings_ratio")
    assert replay_savings_ratio == first_savings_ratio


def test_unknown_computation_id_returns_404(client):
    import uuid

    response = client.get(f"/api/v1/profile/metrics/history/{uuid.uuid4()}")
    assert response.status_code == 404


def test_metrics_are_isolated_per_user(client, db_session):
    client.post("/api/v1/profile", json={"monthly_income": "50000", "fixed_expenses": "10000", "variable_expenses": "5000"})
    client.get("/api/v1/profile/metrics")

    from app.core.user_context import get_current_user

    other_user = User(email="metrics-other-user@example.com")
    db_session.add(other_user)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: other_user
    other_client = TestClient(app)

    # Other user has no profile at all.
    response = other_client.get("/api/v1/profile/metrics")
    assert response.status_code == 404

    history = other_client.get("/api/v1/profile/metrics/history").json()
    assert history == []
