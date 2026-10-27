import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiBaseModel


class HoldingActivityCreate(ApiBaseModel):
    activity_type: Literal["purchase", "redemption", "adjustment"]
    units: Decimal = Field(max_digits=18, decimal_places=6)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    activity_date: date
    note: str | None = Field(default=None, max_length=500)

    @field_validator("activity_date")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > datetime.now(timezone.utc).date():
            raise ValueError("activity_date cannot be in the future")
        return value

    @model_validator(mode="after")
    def _validate_kind(self):
        if self.activity_type in {"purchase", "redemption"} and self.units <= 0:
            raise ValueError("Purchase and redemption units must be greater than zero")
        if self.activity_type in {"purchase", "redemption"} and self.amount is None:
            raise ValueError("Purchase and redemption entries require an amount")
        if self.activity_type == "adjustment" and (self.units == 0 or self.amount is not None):
            raise ValueError("An adjustment requires a non-zero signed unit change and no cash amount")
        return self


class HoldingActivityRead(ApiBaseModel):
    id: uuid.UUID
    activity_type: str
    units_delta: Decimal
    amount: Decimal | None
    activity_date: date
    note: str | None
    created_at: datetime
