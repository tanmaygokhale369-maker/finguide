import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import ApiBaseModel


class HoldingCreate(ApiBaseModel):
    scheme_code: int = Field(gt=0)
    units: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    amount_invested: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    monthly_sip: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class HoldingUpdate(ApiBaseModel):
    units: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    amount_invested: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    monthly_sip: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class HoldingRead(ApiBaseModel):
    id: uuid.UUID
    scheme_code: int
    scheme_name: str
    scheme_category: str | None
    units: Decimal
    amount_invested: Decimal | None
    monthly_sip: Decimal | None
    redemption_proceeds: Decimal
    activity_count: int
    current_nav: Decimal | None
    current_value: Decimal | None
    nav_date: str | None
    valuation_status: str
    created_at: datetime
    updated_at: datetime
