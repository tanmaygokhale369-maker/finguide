"""
Validation schemas.

Brick 08 scope: the read-only view over validated financial field state.
`value`/`confidence` are only populated for statuses that represent a
single usable value (VALID, LOW_CONFIDENCE) — CONFLICTING, INCOMPLETE,
and REJECTED intentionally carry no value, so a careless consumer can't
accidentally treat an unresolved or rejected field as a real number.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from app.models.validation_status import ValidationStatus
from app.schemas.common import ApiBaseModel


class FieldValidationSummaryRead(ApiBaseModel):
    field_name: str
    status: ValidationStatus
    value: Decimal | None
    confidence: Decimal | None
    reason: str | None
    contributing_field_ids: list[uuid.UUID]
    evaluated_at: datetime
