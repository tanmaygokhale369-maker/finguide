"""
Unit tests for app/services/spending_analysis_service.py (Brick 11).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.transaction import Transaction, TransactionCategory, TransactionType
from app.models.user import User
from app.services import spending_analysis_service as service


@pytest.fixture()
def user(db_session):
    u = User(email="spend-test@example.com")
    db_session.add(u)
    db_session.flush()
    return u


def _txn(db_session, user, *, amount, type_, category, d, description=None):
    t = Transaction(
        user_id=user.id,
        amount=Decimal(amount),
        type=type_,
        category=category,
        transaction_date=d,
        description=description,
        source="manual",
    )
    db_session.add(t)
    db_session.flush()
    return t


def test_no_transactions_returns_explicit_empty_state(db_session, user):
    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result.has_data is False
    assert result.transaction_count == 0
    assert result.income_total == Decimal("0.00")
    assert result.category_totals == []
    assert result.trend.status == "INSUFFICIENT_DATA"


def test_end_before_start_raises(db_session, user):
    with pytest.raises(ValueError):
        service.analyze_spending(db_session, user.id, date(2026, 2, 1), date(2026, 1, 1))


def test_income_vs_expense_totals(db_session, user):
    _txn(db_session, user, amount="60000", type_=TransactionType.INCOME, category=TransactionCategory.SALARY, d=date(2026, 1, 5))
    _txn(db_session, user, amount="15000", type_=TransactionType.EXPENSE, category=TransactionCategory.HOUSING, d=date(2026, 1, 10))
    _txn(db_session, user, amount="5000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 15))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.has_data is True
    assert result.transaction_count == 3
    assert result.income_total == Decimal("60000.00")
    assert result.expense_total == Decimal("20000.00")
    assert result.net == Decimal("40000.00")


def test_category_totals_grouped_correctly(db_session, user):
    _txn(db_session, user, amount="1000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 1))
    _txn(db_session, user, amount="2000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 15))
    _txn(db_session, user, amount="500", type_=TransactionType.EXPENSE, category=TransactionCategory.ENTERTAINMENT, d=date(2026, 1, 20))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    by_category = {c.category: c for c in result.category_totals}
    assert by_category[TransactionCategory.GROCERIES].total == Decimal("3000.00")
    assert by_category[TransactionCategory.GROCERIES].transaction_count == 2
    assert by_category[TransactionCategory.ENTERTAINMENT].total == Decimal("500.00")


def test_monthly_totals_bucketed_by_month(db_session, user):
    _txn(db_session, user, amount="1000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 10))
    _txn(db_session, user, amount="1500", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 2, 10))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 2, 28))

    months = {m.month: m for m in result.monthly_totals}
    assert months["2026-01"].expense_total == Decimal("1000.00")
    assert months["2026-02"].expense_total == Decimal("1500.00")


def test_recurring_expense_detected_across_months(db_session, user):
    # Same category + same exact amount in 3 different months -> recurring.
    for month in (1, 2, 3):
        _txn(db_session, user, amount="999.00", type_=TransactionType.EXPENSE, category=TransactionCategory.SUBSCRIPTIONS, d=date(2026, month, 1))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 3, 31))

    assert len(result.recurring_expenses) == 1
    rec = result.recurring_expenses[0]
    assert rec.category == TransactionCategory.SUBSCRIPTIONS
    assert rec.amount == Decimal("999.00")
    assert rec.months == ["2026-01", "2026-02", "2026-03"]


def test_single_occurrence_is_not_recurring(db_session, user):
    _txn(db_session, user, amount="999.00", type_=TransactionType.EXPENSE, category=TransactionCategory.SUBSCRIPTIONS, d=date(2026, 1, 1))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.recurring_expenses == []


def test_different_amounts_same_category_not_recurring(db_session, user):
    _txn(db_session, user, amount="100.00", type_=TransactionType.EXPENSE, category=TransactionCategory.DINING_OUT, d=date(2026, 1, 1))
    _txn(db_session, user, amount="150.00", type_=TransactionType.EXPENSE, category=TransactionCategory.DINING_OUT, d=date(2026, 2, 1))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 2, 28))

    assert result.recurring_expenses == []


def test_unusual_transaction_detected(db_session, user):
    # Three normal entertainment transactions (avg 100), then one far above
    # the 2x-average threshold.
    for d in (1, 8, 15):
        _txn(db_session, user, amount="100.00", type_=TransactionType.EXPENSE, category=TransactionCategory.ENTERTAINMENT, d=date(2026, 1, d))
    spike = _txn(db_session, user, amount="5000.00", type_=TransactionType.EXPENSE, category=TransactionCategory.ENTERTAINMENT, d=date(2026, 1, 22))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    unusual_ids = {u.transaction_id for u in result.unusual_transactions}
    assert spike.id in unusual_ids


def test_unusual_detection_requires_minimum_sample_size(db_session, user):
    # Only 2 transactions in the category -> not enough history to judge
    # "unusual" meaningfully, regardless of how different they are.
    _txn(db_session, user, amount="100.00", type_=TransactionType.EXPENSE, category=TransactionCategory.ENTERTAINMENT, d=date(2026, 1, 1))
    _txn(db_session, user, amount="5000.00", type_=TransactionType.EXPENSE, category=TransactionCategory.ENTERTAINMENT, d=date(2026, 1, 15))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.unusual_transactions == []


def test_trend_increasing(db_session, user):
    _txn(db_session, user, amount="100.00", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 2))
    _txn(db_session, user, amount="500.00", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 28))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.trend.status == "INCREASING"


def test_trend_stable_within_band(db_session, user):
    _txn(db_session, user, amount="1000.00", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 2))
    _txn(db_session, user, amount="1020.00", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 28))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.trend.status == "STABLE"


def test_missing_data_acknowledged_not_assumed_zero_elsewhere(db_session, user):
    """
    A range with no income transactions should report income_total as an
    explicit 0.00 derived from zero matching rows — not confuse "no income
    data" with FinancialProfile's "missing means unknown" rule (Brick 05).
    Transactions are concrete events: absence of a row in range genuinely
    means zero activity in that range, not an unknown value.
    """
    _txn(db_session, user, amount="1000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 10))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.has_data is True
    assert result.income_total == Decimal("0.00")


def test_date_range_is_respected_transactions_outside_excluded(db_session, user):
    _txn(db_session, user, amount="1000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2025, 12, 31))
    _txn(db_session, user, amount="2000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 15))
    _txn(db_session, user, amount="3000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 2, 1))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.transaction_count == 1
    assert result.expense_total == Decimal("2000.00")


def test_analysis_is_reproducible(db_session, user):
    _txn(db_session, user, amount="1234.56", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 10))

    result1 = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))
    result2 = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result1.expense_total == result2.expense_total == Decimal("1234.56")
    assert result1.analysis_version == result2.analysis_version == "v1"


def test_results_are_isolated_per_user(db_session, user):
    other = User(email="other-spend-test@example.com")
    db_session.add(other)
    db_session.flush()

    _txn(db_session, user, amount="1000", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 10))
    _txn(db_session, other, amount="9999", type_=TransactionType.EXPENSE, category=TransactionCategory.GROCERIES, d=date(2026, 1, 10))

    result = service.analyze_spending(db_session, user.id, date(2026, 1, 1), date(2026, 1, 31))

    assert result.transaction_count == 1
    assert result.expense_total == Decimal("1000.00")
