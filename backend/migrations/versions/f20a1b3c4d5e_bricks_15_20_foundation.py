"""Bricks 15-20: evidence, lifecycle audit, feedback, auth, governance.

Revision ID: f20a1b3c4d5e
Revises: e7b2d4c9a1f5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f20a1b3c4d5e"
down_revision: Union[str, None] = "e7b2d4c9a1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("recommendations", sa.Column("model_version", sa.String(100), server_default="deterministic-rules-v1", nullable=False))
    op.add_column("recommendations", sa.Column("prompt_version", sa.String(100), nullable=True))
    op.add_column("recommendations", sa.Column("context_version", sa.String(100), server_default="financial-profile-v1", nullable=False))
    op.create_table(
        "external_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("credibility", sa.Numeric(3, 2), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("relevance", sa.String(500)),
        sa.Column("conflict_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sentiment_label", sa.String(20), nullable=False, server_default="uncertain"),
        sa.Column("sentiment_confidence", sa.Numeric(3, 2)),
        sa.Column("sentiment_model", sa.String(100)),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.UniqueConstraint("user_id", "content_hash", "source_name", name="uq_evidence_user_source_hash"),
    )
    for name, column in (("ix_external_evidence_user_id", "user_id"), ("ix_external_evidence_source_type", "source_type"), ("ix_external_evidence_content_hash", "content_hash"), ("ix_external_evidence_valid_until", "valid_until"), ("ix_external_evidence_verification_status", "verification_status")):
        op.create_index(name, "external_evidence", [column])

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False), sa.Column("rating", sa.String(20)), sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("action IN ('accepted','rejected','ignored')", name="ck_feedback_action"),
        sa.CheckConstraint("rating IS NULL OR rating IN ('helpful','not_helpful','harmful')", name="ck_feedback_rating"),
    )
    op.create_index("ix_recommendation_feedback_user_id", "recommendation_feedback", ["user_id"])
    op.create_index("ix_recommendation_feedback_recommendation_id", "recommendation_feedback", ["recommendation_id"])

    op.create_table(
        "safety_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendation_feedback.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"), sa.Column("investigation_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_safety_incidents_user_id", "safety_incidents", ["user_id"])
    op.create_index("ix_safety_incidents_recommendation_id", "safety_incidents", ["recommendation_id"])

    op.create_table(
        "evaluation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("evaluation_type", sa.String(80), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("metric_name", sa.String(100), nullable=False), sa.Column("numerator", sa.Integer(), nullable=False),
        sa.Column("denominator", sa.Integer(), nullable=False), sa.Column("result", sa.Numeric(8, 6)),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("numerator >= 0 AND denominator >= numerator", name="ck_evaluation_counts"),
    )
    op.create_index("ix_evaluation_records_evaluation_type", "evaluation_records", ["evaluation_type"])
    op.create_index("ix_evaluation_records_user_id", "evaluation_records", ["user_id"])

    op.create_table(
        "recommendation_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state", sa.String(30)), sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_recommendation_audit_events_user_id", "recommendation_audit_events", ["user_id"])
    op.create_index("ix_recommendation_audit_events_recommendation_id", "recommendation_audit_events", ["recommendation_id"])

    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(80), nullable=False), sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_index("ix_recommendation_audit_events_recommendation_id", table_name="recommendation_audit_events")
    op.drop_index("ix_recommendation_audit_events_user_id", table_name="recommendation_audit_events")
    op.drop_table("recommendation_audit_events")
    op.drop_index("ix_evaluation_records_evaluation_type", table_name="evaluation_records")
    op.drop_index("ix_evaluation_records_user_id", table_name="evaluation_records")
    op.drop_table("evaluation_records")
    op.drop_index("ix_safety_incidents_recommendation_id", table_name="safety_incidents")
    op.drop_index("ix_safety_incidents_user_id", table_name="safety_incidents")
    op.drop_table("safety_incidents")
    op.drop_index("ix_recommendation_feedback_recommendation_id", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_user_id", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
    for name in ("ix_external_evidence_verification_status", "ix_external_evidence_valid_until", "ix_external_evidence_content_hash", "ix_external_evidence_source_type", "ix_external_evidence_user_id"):
        op.drop_index(name, table_name="external_evidence")
    op.drop_table("external_evidence")
    op.drop_column("recommendations", "context_version")
    op.drop_column("recommendations", "prompt_version")
    op.drop_column("recommendations", "model_version")
    op.drop_column("users", "password_hash")
