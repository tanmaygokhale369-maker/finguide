"""User-entered mutual-fund positions; quotes are always fetched separately."""
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class MutualFundHolding(TimestampMixin, Base):
    __tablename__ = "mutual_fund_holdings"
    __table_args__ = (
        CheckConstraint("units > 0", name="ck_mf_holding_units_positive"),
        CheckConstraint("amount_invested IS NULL OR amount_invested >= 0", name="ck_mf_holding_invested_nonnegative"),
        CheckConstraint("monthly_sip IS NULL OR monthly_sip >= 0", name="ck_mf_holding_sip_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scheme_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scheme_name: Mapped[str] = mapped_column(String(300), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    amount_invested: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2))
    monthly_sip: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2))
    redemption_proceeds: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2), nullable=False, default=Decimal("0"))
