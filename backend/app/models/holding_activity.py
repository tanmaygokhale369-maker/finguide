"""Manual, dated activity records for mutual-fund holdings."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class HoldingActivity(TimestampMixin, Base):
    __tablename__ = "holding_activities"
    __table_args__ = (
        CheckConstraint("activity_type IN ('opening_balance','purchase','redemption','adjustment')", name="ck_holding_activity_type"),
        CheckConstraint("units_delta <> 0", name="ck_holding_activity_units_nonzero"),
        CheckConstraint("(activity_type = 'redemption' AND units_delta < 0) OR (activity_type <> 'redemption' AND units_delta > 0) OR activity_type = 'adjustment'", name="ck_holding_activity_sign"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_holding_activity_amount_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mutual_fund_holdings.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    units_delta: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2))
    activity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
