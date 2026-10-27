"""
ExtractedField model.

Brick 07 scope: stores every extraction candidate — including multiple,
conflicting candidates for the same field from the same or different
messages — with the metadata required for traceability (source text,
confidence, extraction method, timestamp). Rows here are candidates,
never automatically applied to FinancialProfile.

Brick 08 addition: `validation_status` records this specific row's own
validity (VALID/LOW_CONFIDENCE/CONFLICTING/REJECTED — see
app/models/validation_status.py for why INCOMPLETE and
REQUIRES_CLARIFICATION don't apply at the row level) after
app/services/validation_service.py evaluates it against range checks and
the rest of this user's history for the same field. Turning validated
data into FinancialProfile fields is still not done here — that is a
deliberate, separate, explicit action via the profile API.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.validation_status import ValidationStatus


class ExtractedField(TimestampMixin, Base):
    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized for direct ownership checks/queries without joining
    # through messages -> conversations -> users every time.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    field_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(precision=3, scale=2), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ambiguity_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        default=ValidationStatus.LOW_CONFIDENCE,
        server_default=ValidationStatus.LOW_CONFIDENCE.value,
        nullable=False,
    )
