"""
Explanation schema — Brick 14. Read-only; nothing here is ever written
by a client.
"""

import uuid

from app.schemas.common import ApiBaseModel


class UserDataUsedRead(ApiBaseModel):
    metric_name: str | None
    metric_value: str | None
    formula: str | None
    input_values: dict
    calculation_version: str | None
    calculated_at: str | None


class ExplanationRead(ApiBaseModel):
    recommendation_id: uuid.UUID
    what: str
    why: str
    user_data_used: UserDataUsedRead | None
    external_evidence: list
    assumptions: list[str]
    confidence: str
    confidence_note: str
    limitations: list[str]
