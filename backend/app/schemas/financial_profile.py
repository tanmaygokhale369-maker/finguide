"""
FinancialProfile schemas.

Brick 05 scope: request/response shapes for the profile API. Validation
here is deliberately basic (types, non-negative amounts) — contradiction
detection, confidence scoring, and status tracking (VALID/INCOMPLETE/
CONFLICTING/etc.) are Brick 08's job, not this one's.

`FinancialProfileUpdate` is used for both creation and partial updates.
Every field defaults to unset (not `None`) so the service layer can use
`model_dump(exclude_unset=True)` to tell "field not mentioned" apart from
"field explicitly set to null" — the former leaves existing data alone,
the latter intentionally clears a value back to unknown. Neither ever
gets silently defaulted to zero.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import ApiBaseModel


class FinancialProfileUpdate(ApiBaseModel):
    monthly_income: Decimal | None = Field(default=None, ge=0)
    fixed_expenses: Decimal | None = Field(default=None, ge=0)
    variable_expenses: Decimal | None = Field(default=None, ge=0)
    savings: Decimal | None = Field(default=None, ge=0)
    debt: Decimal | None = Field(default=None, ge=0)
    dependents: int | None = Field(default=None, ge=0)
    emergency_fund_amount: Decimal | None = Field(default=None, ge=0)
    has_insurance: bool | None = None
    existing_investments_amount: Decimal | None = Field(default=None, ge=0)
    risk_preference: str | None = Field(default=None, max_length=50)
    investment_horizon_years: int | None = Field(default=None, ge=0)
    financial_goals: str | None = None


class FinancialProfileRead(ApiBaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    monthly_income: Decimal | None
    fixed_expenses: Decimal | None
    variable_expenses: Decimal | None
    savings: Decimal | None
    debt: Decimal | None
    dependents: int | None
    emergency_fund_amount: Decimal | None
    has_insurance: bool | None
    existing_investments_amount: Decimal | None
    risk_preference: str | None
    investment_horizon_years: int | None
    financial_goals: str | None
    created_at: datetime
    updated_at: datetime
