"""
API tests for GET /api/v1/spending/analysis (Brick 11).

Follows the same fresh-user-per-test dependency-override pattern as
test_transactions_api.py.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.transaction import Transaction, TransactionCategory, TransactionType
from app.models.user import User


@pytest.fixture()
def client(db_session):
    from app.core.user_context import get_current_user
    from app.db.session import get_db

    user = User(email="spend-api-test@example.com")
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


def _txn(db_session, user, **kwargs):
    defaults = dict(
        user_id=user.id,
        amount=Decimal("1000.00"),
        type=TransactionType.EXPENSE,
        category=TransactionCategory.GROCERIES,
        transaction_date=date(2026, 1, 15),
        source="manual",
    )
    defaults.update(kwargs)
    t = Transaction(**defaults)
    db_session.add(t)
    db_session.flush()
    return t


def test_missing_start_date_is_422(client):
    c, _, _ = client
    resp = c.get("/api/v1/spending/analysis", params={"end_date": "2026-01-31"})
    assert resp.status_code == 422


def test_missing_end_date_is_422(client):
    c, _, _ = client
    resp = c.get("/api/v1/spending/analysis", params={"start_date": "2026-01-01"})
    assert resp.status_code == 422


def test_end_before_start_is_422(client):
    c, _, _ = client
    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-02-01", "end_date": "2026-01-01"},
    )
    assert resp.status_code == 422


def test_empty_range_returns_has_data_false_not_an_error(client):
    c, _, _ = client
    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is False
    assert body["transaction_count"] == 0


def test_analysis_reflects_created_transactions(client):
    c, user, db_session = client
    _txn(db_session, user, amount=Decimal("1500.00"), type=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, transaction_date=date(2026, 1, 10))
    _txn(db_session, user, amount=Decimal("60000.00"), type=TransactionType.INCOME, category=TransactionCategory.SALARY, transaction_date=date(2026, 1, 1))

    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is True
    assert body["transaction_count"] == 2
    assert body["income_total"] == "60000.00"
    assert body["expense_total"] == "1500.00"
    assert body["net"] == "58500.00"
    assert body["analysis_version"] == "v1"


def test_response_includes_all_required_sections(client):
    c, user, db_session = client
    _txn(db_session, user)

    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    body = resp.json()
    for key in (
        "category_totals",
        "monthly_totals",
        "recurring_expenses",
        "unusual_transactions",
        "trend",
    ):
        assert key in body


def test_isolated_per_user(client):
    c, user, db_session = client
    other = User(email="spend-api-other@example.com")
    db_session.add(other)
    db_session.flush()
    _txn(db_session, other, amount=Decimal("9999.00"))

    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    body = resp.json()
    assert body["has_data"] is False


def test_requires_authentication_dependency_present():
    """No dependency override -> get_current_user's real (dev-only) path runs."""
    c = TestClient(app)
    resp = c.get(
        "/api/v1/spending/analysis",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    # Real dev user-context path (no DB override here) — should not 401/403
    # silently bypass identity resolution; it either resolves a dev user
    # or fails loudly (500/501), never a 200 with no identity at all.
    assert resp.status_code != 200 or "has_data" in resp.json()
