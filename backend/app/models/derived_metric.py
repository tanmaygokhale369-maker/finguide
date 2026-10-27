"""
DerivedMetric model.

Brick 09 scope: every row is an immutable record of one metric
computation, carrying exactly the metadata the architecture docs
require: metric name, value, formula, input values, calculation
version, and a timestamp (via TimestampMixin's created_at, exposed as
`calculated_at` — see the property below).

Rows are never updated or overwritten. Each call to
metrics_service.compute_and_store_metrics creates a new batch of rows
sharing one `computation_id`, so the full history of what this user's
derived metrics looked like at any point in time is preserved — this is
what "profile versioning" means in this brick, since FinancialProfile
itself (Brick 04/05) remains a single mutable current-state row.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.metric_status import MetricStatus


class DerivedMetric(TimestampMixin, Base):
    __tablename__ = "derived_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    financial_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Groups every metric produced by one compute_and_store_metrics call
    # into a single retrievable snapshot/"version".
    computation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    metric_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[MetricStatus] = mapped_column(ENUM(MetricStatus, name="metric_status"), nullable=False)
    # Higher scale than money fields (Numeric(14,2)) — ratios need more
    # decimal precision, not currency-style rounding.
    value: Mapped[float | None] = mapped_column(Numeric(precision=18, scale=6), nullable=True)
    formula: Mapped[str] = mapped_column(String(255), nullable=False)
    # Exact string representations of the Decimal inputs actually used
    # (or actually present, if INCOMPLETE) — never floats, so the
    # calculation is exactly reproducible from this record alone.
    input_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_inputs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False)

    @property
    def calculated_at(self) -> datetime:
        """Alias matching the architecture docs' exact vocabulary for
        this timestamp, without a redundant duplicate DB column."""
        return self.created_at
