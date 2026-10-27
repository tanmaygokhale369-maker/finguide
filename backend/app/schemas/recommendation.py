"""
Recommendation schemas — Bricks 12 (generation) and 13 (evaluation).

Read-only from the API's perspective: there is no client-writable
Create/Update schema. A Recommendation row only ever comes into
existence via POST /recommendations/generate (the deterministic rule
engine), and only ever changes via POST /recommendations/evaluate* (the
deterministic safety/suitability gate) — never arbitrary client input,
consistent with "AI generation never directly becomes the final
user-facing recommendation" applying equally to "a client never gets to
set one's content or decision directly."
"""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.common import ApiBaseModel


class RecommendationRead(ApiBaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    category: str
    title: str
    reason: str
    confidence: Decimal
    risk_level: str
    state: str
    suitability_status: str | None
    source_references: list
    based_on: dict
    rule_id: str
    policy_version: str
    model_version: str = "deterministic-rules-v1"
    prompt_version: str | None = None
    context_version: str = "financial-profile-v1"
    created_at: datetime
    # Brick 13 fields — null/[] until the safety gate has evaluated this row.
    safety_explanation: str | None
    safety_checks: list
    # Computed at read time by comparing the immutable recommendation's
    # source computation with the user's latest profile computation.
    current_for_profile: bool = True


class SkippedRuleRead(ApiBaseModel):
    rule_id: str
    reason: str


class GenerationResultRead(ApiBaseModel):
    context_status: str
    candidates: list[RecommendationRead]
    skipped: list[SkippedRuleRead]


class SafetyCheckRead(ApiBaseModel):
    check: str
    passed: bool
    detail: str


class EvaluationResultRead(ApiBaseModel):
    recommendation_id: uuid.UUID
    decision: str
    state: str
    explanation: str
    checks: list[SafetyCheckRead]
