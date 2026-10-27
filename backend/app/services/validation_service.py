"""
Validation service.

Brick 08 scope: turn Brick 07's raw extraction candidates into validated
financial state, per the canonical flow:

    Data Extraction -> Confidence + Validation -> Financial Context Completeness

Two distinct things happen here, at two different granularities:

1. `revalidate_field` assigns a `validation_status` to every individual
   ExtractedField row for one (user, field_name) — VALID, LOW_CONFIDENCE,
   CONFLICTING, or REJECTED. This re-evaluates the *entire* history for
   that field whenever new data arrives, so a contradiction between a
   value mentioned today and one mentioned last week is caught, not just
   contradictions within a single message (that narrower case is Brick
   07's `is_ambiguous` flag on a single extraction call).

2. `get_field_summary` / `get_all_field_summaries` compute a field-level
   view across that same history — "what do we currently believe about
   this field, and what should happen next" — which is where INCOMPLETE
   (no data at all) and REQUIRES_CLARIFICATION (conflicting data; ask
   the user) apply. Nothing here writes to FinancialProfile — turning a
   validated summary into profile data remains an explicit, separate
   action via the profile API.

Rule 3 (Confidence matters) and Rule 9 (Safety beats personalization)
both cash out concretely here: REJECTED rows are never selected as the
"current best value" for a field, no matter how new they are.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.extracted_field import ExtractedField
from app.models.validation_status import ValidationStatus

# Every field Brick 07 knows how to extract is tracked here. A field
# absent from this dict is not validated (and not reported as
# INCOMPLETE) — it simply isn't part of this brick's scope yet.
RANGE_BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "monthly_income": (Decimal(0), Decimal(10_000_000)),
    "monthly_expenses": (Decimal(0), Decimal(10_000_000)),
    "debt": (Decimal(0), Decimal(100_000_000)),
    "savings": (Decimal(0), Decimal(100_000_000)),
    "dependents": (Decimal(0), Decimal(20)),
}

TRACKED_FIELDS: list[str] = list(RANGE_BOUNDS.keys())


def _in_range(field_name: str, value: Decimal) -> bool:
    low, high = RANGE_BOUNDS[field_name]
    return low <= value <= high


def revalidate_field(db: Session, user_id: uuid.UUID, field_name: str) -> None:
    """
    Recomputes `validation_status` for every ExtractedField row this user
    has for `field_name`. Idempotent — safe to call repeatedly, and
    always called with the full history, not just new rows, so an old
    row can become CONFLICTING when a new contradicting value shows up.
    """
    if field_name not in RANGE_BOUNDS:
        return

    rows = db.query(ExtractedField).filter_by(user_id=user_id, field_name=field_name).all()
    if not rows:
        return

    in_range_rows = [row for row in rows if _in_range(field_name, row.value)]
    distinct_values = {row.value for row in in_range_rows}
    has_conflict = len(distinct_values) > 1

    for row in rows:
        if not _in_range(field_name, row.value):
            row.validation_status = ValidationStatus.REJECTED
        elif has_conflict:
            row.validation_status = ValidationStatus.CONFLICTING
        elif row.confidence < Decimal(str(settings.low_confidence_threshold)):
            row.validation_status = ValidationStatus.LOW_CONFIDENCE
        else:
            row.validation_status = ValidationStatus.VALID


@dataclass(frozen=True)
class FieldValidationSummary:
    field_name: str
    status: ValidationStatus
    value: Decimal | None
    confidence: Decimal | None
    reason: str | None
    contributing_field_ids: list[uuid.UUID]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def get_field_summary(db: Session, user_id: uuid.UUID, field_name: str) -> FieldValidationSummary:
    rows = (
        db.query(ExtractedField)
        .filter_by(user_id=user_id, field_name=field_name)
        .order_by(ExtractedField.created_at.desc())
        .all()
    )

    if not rows:
        return FieldValidationSummary(
            field_name=field_name,
            status=ValidationStatus.INCOMPLETE,
            value=None,
            confidence=None,
            reason="No information has been provided for this field yet.",
            contributing_field_ids=[],
        )

    conflicting = [r for r in rows if r.validation_status == ValidationStatus.CONFLICTING]
    if conflicting:
        return FieldValidationSummary(
            field_name=field_name,
            status=ValidationStatus.REQUIRES_CLARIFICATION,
            value=None,
            confidence=None,
            reason=(
                f"Multiple differing values have been reported for '{field_name}'. "
                "Please clarify the correct current value."
            ),
            contributing_field_ids=[r.id for r in conflicting],
        )

    usable = [r for r in rows if r.validation_status in (ValidationStatus.VALID, ValidationStatus.LOW_CONFIDENCE)]
    if usable:
        best = max(usable, key=lambda r: (r.confidence, r.created_at))
        return FieldValidationSummary(
            field_name=field_name,
            status=best.validation_status,
            value=best.value,
            confidence=best.confidence,
            reason=None if best.validation_status == ValidationStatus.VALID else "Confidence is below the configured threshold.",
            contributing_field_ids=[best.id],
        )

    # Only REJECTED rows exist for this field.
    rejected = [r for r in rows if r.validation_status == ValidationStatus.REJECTED]
    return FieldValidationSummary(
        field_name=field_name,
        status=ValidationStatus.REJECTED,
        value=None,
        confidence=None,
        reason=f"All reported values for '{field_name}' were outside the plausible range.",
        contributing_field_ids=[r.id for r in rejected],
    )


def get_all_field_summaries(db: Session, user_id: uuid.UUID) -> list[FieldValidationSummary]:
    return [get_field_summary(db, user_id, field_name) for field_name in TRACKED_FIELDS]
