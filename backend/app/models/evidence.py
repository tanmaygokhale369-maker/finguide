"""Provenance-bearing external evidence; stored content is always untrusted."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class ExternalEvidence(TimestampMixin, Base):
    __tablename__ = "external_evidence"
    __table_args__ = (UniqueConstraint("user_id", "content_hash", "source_name", name="uq_evidence_user_source_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    credibility: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    relevance: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conflict_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=False, default="uncertain")
    sentiment_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    sentiment_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified", index=True)
