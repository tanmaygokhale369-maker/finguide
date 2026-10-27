"""
Transaction model.

Brick 10 scope: full CRUD API (see app/api/v1/transactions.py) and the
controlled category taxonomy this file defines.

Category taxonomy note: the plan docs require "a controlled category
taxonomy" for transactions but don't specify one. The list below is a
reasonable, clearly-scoped starter set (income + expense + a neutral
fallback) — not a canonical or exhaustive standard. It's easy to extend;
changing it is a migration, same as any other controlled vocabulary in
this app (TransactionType, ValidationStatus, etc.).
"""

import enum
import uuid
from datetime import date as date_type

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin

MONEY = Numeric(precision=14, scale=2)


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCategory(str, enum.Enum):
    # Income
    SALARY = "salary"
    BUSINESS_INCOME = "business_income"
    INVESTMENT_INCOME = "investment_income"
    RENTAL_INCOME = "rental_income"
    GIFT_RECEIVED = "gift_received"
    REFUND = "refund"
    OTHER_INCOME = "other_income"
    # Expense
    HOUSING = "housing"
    UTILITIES = "utilities"
    GROCERIES = "groceries"
    TRANSPORTATION = "transportation"
    HEALTHCARE = "healthcare"
    INSURANCE = "insurance"
    DEBT_PAYMENT = "debt_payment"
    DINING_OUT = "dining_out"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    EDUCATION = "education"
    PERSONAL_CARE = "personal_care"
    SUBSCRIPTIONS = "subscriptions"
    TRAVEL = "travel"
    OTHER_EXPENSE = "other_expense"
    # Neutral — an explicit, valid choice rather than NULL, so "category"
    # remains a required, always-present classification instead of an
    # optional financial fact that could be silently missing.
    UNCATEGORIZED = "uncategorized"


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount: Mapped[float] = mapped_column(MONEY, nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"), nullable=False)
    category: Mapped[TransactionCategory] = mapped_column(
        Enum(TransactionCategory, name="transaction_category"), nullable=False, index=True
    )
    transaction_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Server-controlled, never client-writable — see the create/update
    # schemas in app/schemas/transaction.py. "manual" for every row this
    # brick creates; future bricks (CSV import, bank integration) set
    # their own values through their own code paths, not client input.
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    # 0.00-1.00 confidence when a category was assigned by AI (a future
    # brick). NULL for manual entry (this brick), where confidence does
    # not apply — never defaulted to a number.
    confidence: Mapped[float | None] = mapped_column(Numeric(precision=3, scale=2), nullable=True)
