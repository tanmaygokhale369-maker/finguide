"""
FinancialProfile model.

Brick 04 scope: DB structure only. Every financial field is nullable —
per the project's data rule, missing income/debt/savings/etc. must never
be silently treated as zero. Validation, derived metrics (savings ratio,
debt-to-income, etc.), and the API surface for reading/writing this data
belong to Brick 05 (User/Profile APIs) and Brick 09 (Financial Profile /
derived metrics), not here.

Monetary fields use Numeric (exact, fixed-point), never Float, per the
architecture's non-negotiable rule against floating-point money.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin

MONEY = Numeric(precision=14, scale=2)


class FinancialProfile(TimestampMixin, Base):
    __tablename__ = "financial_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # Every field below is nullable on purpose: unknown is not zero.
    monthly_income: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    fixed_expenses: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    variable_expenses: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    savings: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    debt: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    dependents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emergency_fund_amount: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    has_insurance: Mapped[bool | None] = mapped_column(nullable=True)
    existing_investments_amount: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    risk_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    investment_horizon_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    financial_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
