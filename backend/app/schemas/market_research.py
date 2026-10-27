"""Request models for goal-oriented, source-attributed research."""

from decimal import Decimal

from pydantic import Field

from app.schemas.common import ApiBaseModel


class MutualFundGoalPlanRequest(ApiBaseModel):
    goal_name: str = Field(min_length=2, max_length=120)
    target_amount: Decimal = Field(gt=0, le=Decimal("1000000000000"))
    current_savings: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    years: int = Field(ge=1, le=50)
