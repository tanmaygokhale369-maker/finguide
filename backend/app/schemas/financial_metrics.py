"""
Financial metrics schemas.

Brick 09 scope: read shapes for derived metrics. `value` is only
populated when status == COMPUTED — INCOMPLETE and NOT_COMPUTABLE
intentionally carry no value, same pattern as validation.py's
FieldValidationSummaryRead, so a careless consumer can't accidentally
treat an uncomputed metric as a real number.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from app.models.metric_status import MetricStatus
from app.schemas.common import ApiBaseModel


class DerivedMetricRead(ApiBaseModel):
    id: uuid.UUID
    computation_id: uuid.UUID
    metric_name: str
    status: MetricStatus
    value: Decimal | None
    formula: str
    input_values: dict[str, str]
    missing_inputs: list[str]
    calculation_version: str
    calculated_at: datetime


class ComputationSummary(ApiBaseModel):
    computation_id: uuid.UUID
    calculated_at: datetime
