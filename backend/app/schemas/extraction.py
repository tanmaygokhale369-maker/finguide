"""
ExtractedField schema.

Brick 07 scope: read-only representation of an extraction candidate.
There is no write/create schema — extraction candidates are only ever
produced by the extraction engine, never submitted directly by a client.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.common import ApiBaseModel


class ExtractedFieldRead(ApiBaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    field_name: str
    value: Decimal
    source_text: str
    confidence: Decimal
    extraction_method: str
    is_ambiguous: bool
    ambiguity_reason: str | None
    created_at: datetime
