from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import FinancialProfile, Transaction, TransactionCategory, TransactionType, User


def test_create_and_read_user(db_session):
    user = User(email="alice@example.com", full_name="Alice")
    db_session.add(user)
    db_session.flush()

    fetched = db_session.get(User, user.id)
    assert fetched is not None
    assert fetched.email == "alice@example.com"
    assert fetched.is_active is True
    assert fetched.created_at is not None


def test_user_email_must_be_unique(db_session):
    db_session.add(User(email="dup@example.com"))
    db_session.flush()

    db_session.add(User(email="dup@example.com"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_financial_profile_missing_fields_stay_null_not_zero(db_session):
    """Core data rule: missing debt/savings/etc. must be NULL, never 0."""
    user = User(email="bob@example.com")
    db_session.add(user)
    db_session.flush()

    profile = FinancialProfile(user_id=user.id, monthly_income=Decimal("65000.00"))
    db_session.add(profile)
    db_session.flush()

    fetched = db_session.get(FinancialProfile, profile.id)
    assert fetched.monthly_income == Decimal("65000.00")
    assert fetched.debt is None
    assert fetched.savings is None
    assert fetched.dependents is None


def test_financial_profile_money_field_is_exact_decimal_not_float(db_session):
    user = User(email="carol@example.com")
    db_session.add(user)
    db_session.flush()

    profile = FinancialProfile(user_id=user.id, monthly_income=Decimal("12345.67"))
    db_session.add(profile)
    db_session.flush()
    db_session.refresh(profile)

    assert isinstance(profile.monthly_income, Decimal)
    assert profile.monthly_income == Decimal("12345.67")


def test_one_financial_profile_per_user(db_session):
    user = User(email="dave@example.com")
    db_session.add(user)
    db_session.flush()

    db_session.add(FinancialProfile(user_id=user.id))
    db_session.flush()

    db_session.add(FinancialProfile(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_create_and_update_transaction(db_session):
    user = User(email="erin@example.com")
    db_session.add(user)
    db_session.flush()

    txn = Transaction(
        user_id=user.id,
        amount=Decimal("1500.00"),
        type=TransactionType.EXPENSE,
        category=TransactionCategory.GROCERIES,
        transaction_date=date(2026, 1, 15),
        source="manual",
    )
    db_session.add(txn)
    db_session.flush()

    fetched = db_session.get(Transaction, txn.id)
    assert fetched.amount == Decimal("1500.00")
    assert fetched.type == TransactionType.EXPENSE

    fetched.category = TransactionCategory.HOUSING
    db_session.flush()
    db_session.refresh(fetched)
    assert fetched.category == TransactionCategory.HOUSING


def test_transaction_requires_a_valid_user(db_session):
    import uuid

    txn = Transaction(
        user_id=uuid.uuid4(),
        amount=Decimal("100.00"),
        type=TransactionType.INCOME,
        category=TransactionCategory.SALARY,
        transaction_date=date(2026, 1, 1),
    )
    db_session.add(txn)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_user_cascades_to_profile_and_transactions(db_session):
    user = User(email="frank@example.com")
    db_session.add(user)
    db_session.flush()

    db_session.add(FinancialProfile(user_id=user.id))
    db_session.add(
        Transaction(
            user_id=user.id,
            amount=Decimal("50.00"),
            type=TransactionType.EXPENSE,
            category=TransactionCategory.OTHER_EXPENSE,
            transaction_date=date(2026, 1, 1),
        )
    )
    db_session.flush()

    db_session.delete(user)
    db_session.flush()

    assert db_session.query(FinancialProfile).filter_by(user_id=user.id).first() is None
    assert db_session.query(Transaction).filter_by(user_id=user.id).first() is None


def test_db_itself_rejects_an_invalid_category_not_just_python(db_session):
    """
    Defense in depth: Python's enum already prevents constructing an
    invalid TransactionCategory, but this proves the *database* also
    enforces the taxonomy — via raw SQL, bypassing the ORM/Pydantic
    entirely — so a bug in application code couldn't silently insert an
    uncontrolled category value.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DataError

    user = User(email="db-enum-check@example.com")
    db_session.add(user)
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO transactions (id, user_id, amount, type, category, transaction_date, source, "
                "created_at, updated_at) "
                "VALUES (gen_random_uuid(), :user_id, 10.00, 'EXPENSE', 'NOT_A_REAL_CATEGORY', CURRENT_DATE, "
                "'manual', now(), now())"
            ),
            {"user_id": user.id},
        )
        db_session.flush()
