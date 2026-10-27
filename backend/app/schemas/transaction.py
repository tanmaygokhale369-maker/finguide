"""
Transaction schemas.

Brick 10 scope: `source` and `confidence` are intentionally absent from
both Create and Update — they're server-controlled provenance fields
(see the model docstring), never client-writable. Every other field is
included in Update so a PATCH can change any of them, using the same
exclude_unset pattern as FinancialProfileUpdate: only fields present in
the request body are changed.
"""

import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.models.transaction import TransactionCategory, TransactionType
from app.schemas.common import ApiBaseModel


class TransactionCreate(ApiBaseModel):
    amount: Decimal = Field(gt=0)
    type: TransactionType
    category: TransactionCategory
    transaction_date: date_type
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("transaction_date")
    @classmethod
    def _not_in_the_future(cls, value: date_type) -> date_type:
        if value > datetime.now(timezone.utc).date():
            raise ValueError("transaction_date cannot be in the future")
        return value


class TransactionUpdate(ApiBaseModel):
    """
    Every field is optional to *omit* (so a PATCH can touch just one).
    amount/type/category/transaction_date have no legitimate "clear to
    unknown" meaning (unlike description), so a model-level validator
    below explicitly rejects sending one of them as `null` — a clean 422
    instead of reaching the database and violating its NOT NULL
    constraint (which would surface as an ugly generic 500).
    """

    amount: Decimal | None = Field(default=None, gt=0)
    type: TransactionType | None = None
    category: TransactionCategory | None = None
    transaction_date: date_type | None = None
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("transaction_date")
    @classmethod
    def _not_in_the_future(cls, value: date_type | None) -> date_type | None:
        if value is not None and value > datetime.now(timezone.utc).date():
            raise ValueError("transaction_date cannot be in the future")
        return value

    @model_validator(mode="after")
    def _reject_explicit_null_for_required_fields(self) -> "TransactionUpdate":
        for field_name in ("amount", "type", "category", "transaction_date"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be explicitly set to null — it has no meaning as 'unknown'")
        return self


class TransactionRead(ApiBaseModel):
    id: uuid.UUID
    amount: Decimal
    type: TransactionType
    category: TransactionCategory
    transaction_date: date_type
    description: str | None
    source: str
    confidence: Decimal | None
    created_at: datetime
    updated_at: datetime
