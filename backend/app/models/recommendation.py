"""
Recommendation model.

Brick 12 scope: candidate generation ONLY (see
app/services/recommendation_service.py). Every row this brick creates
starts in state=CANDIDATE and must never be treated as an approved,
user-facing financial recommendation — Architecture v1.1 LOCK's
constraint #1: "AI generation never directly becomes the final
user-facing financial recommendation." No AI/LLM is even involved yet —
candidates here are 100% deterministic rule-based threshold checks
against Brick 09's already-computed, already-validated derived metrics
(same rule-based posture as the Brick 06 chatbot) — but the lifecycle
discipline is identical regardless of what generated the candidate.

suitability_status stays NULL and state stays CANDIDATE for every row
the generator writes. The safety gate owns review decisions; the
presentation and feedback APIs own the later lifecycle transitions.

source_references vs. based_on — two distinct kinds of provenance:
- source_references: evidence actually used. Always [] for current
  deterministic rules because no verified provider is configured.
  User-submitted evidence remains unverified and is never consumed.
- based_on: internal traceability per Rule 7 — exactly which derived
  metric(s)/computation_id/financial_profile drove this candidate, so a
  future developer can reconstruct "why did FinGuide+ produce this?"
  without guessing.
"""

import enum
import uuid

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class RecommendationCategory(str, enum.Enum):
    EMERGENCY_FUND = "emergency_fund"
    SAVINGS = "savings"
    DEBT = "debt"
    BUDGETING = "budgeting"


class RecommendationRiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationState(str, enum.Enum):
    """Full lifecycle per Architecture v1.1 LOCK / Implementation Plan.
    Brick 12 only ever writes CANDIDATE. Every other value exists here
    so the column's type is correct from the start, not because this
    brick's code can produce them."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    APPROVED = "approved"
    MODIFIED = "modified"
    BLOCKED = "blocked"
    CLARIFY = "clarify"
    ESCALATE = "escalate"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IGNORED = "ignored"
    EVALUATED = "evaluated"


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[RecommendationCategory] = mapped_column(
        ENUM(RecommendationCategory, name="recommendation_category"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Deterministic threshold rules either fire or don't — 1.00 for every
    # candidate this brick produces (see service module docstring for why
    # this isn't a probabilistic score yet). The column allows a narrower
    # range for future, genuinely probabilistic generators.
    confidence: Mapped[float] = mapped_column(Numeric(precision=3, scale=2), nullable=False)
    risk_level: Mapped[RecommendationRiskLevel] = mapped_column(
        ENUM(RecommendationRiskLevel, name="recommendation_risk_level"), nullable=False
    )
    state: Mapped[RecommendationState] = mapped_column(
        ENUM(RecommendationState, name="recommendation_state"),
        nullable=False,
        default=RecommendationState.CANDIDATE,
        index=True,
    )
    # NULL until Brick 13 reviews this candidate — never set by this brick.
    # Brick 13 stores the exact safety decision here (one of Pack 02's six:
    # APPROVE/CLARIFY/EDUCATE/LIMIT/BLOCK/ESCALATE) — finer-grained than
    # `state`, which only has lifecycle-vocabulary values. See
    # app/services/safety_suitability_service.py's module docstring for
    # why these two fields intentionally carry different vocabularies.
    suitability_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Brick 13's human-readable explanation of its decision and the
    # ordered list of checks it ran (each: {check, result, detail}) — the
    # audit trail Pack 02 requires alongside safety_status. Both NULL/[]
    # until Brick 13 evaluates this row.
    safety_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_checks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    source_references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    based_on: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Which deterministic rule produced this row, and its version — the
    # recommendation-generation equivalent of Brick 09's calculation_version.
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic-rules-v1")
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_version: Mapped[str] = mapped_column(String(100), nullable=False, default="financial-profile-v1")
