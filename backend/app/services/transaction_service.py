"""
Transaction service.

Brick 10 scope: user-scoped CRUD. Every function takes user_id explicitly
and filters by it — callers (the API layer) always pass
current_user.id from get_current_user, never a client-supplied id.
"""

import uuid
from datetime import date as date_type

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionCategory, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionUpdate


class TransactionNotFoundError(Exception):
    pass


def create_transaction(db: Session, user_id: uuid.UUID, data: TransactionCreate) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        amount=data.amount,
        type=data.type,
        category=data.category,
        transaction_date=data.transaction_date,
        description=data.description,
        source="manual",  # never client-controlled — see schema docstring
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_transaction(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
    transaction = (
        db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
    )
    if transaction is None:
        raise TransactionNotFoundError(f"No transaction {transaction_id} found for this user.")
    return transaction


def list_transactions(
    db: Session,
    user_id: uuid.UUID,
    *,
    type: TransactionType | None = None,
    category: TransactionCategory | None = None,
    start_date: date_type | None = None,
    end_date: date_type | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    if type is not None:
        query = query.filter(Transaction.type == type)
    if category is not None:
        query = query.filter(Transaction.category == category)
    if start_date is not None:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.filter(Transaction.transaction_date <= end_date)

    return (
        query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_transaction(
    db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID, data: TransactionUpdate
) -> Transaction:
    transaction = get_transaction(db, user_id, transaction_id)  # raises TransactionNotFoundError if missing/not owned

    provided_fields = data.model_dump(exclude_unset=True)
    for field_name, value in provided_fields.items():
        setattr(transaction, field_name, value)

    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
    transaction = get_transaction(db, user_id, transaction_id)  # raises TransactionNotFoundError if missing/not owned
    db.delete(transaction)
    db.commit()
