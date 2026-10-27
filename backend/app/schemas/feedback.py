from pydantic import Field
from app.schemas.common import ApiBaseModel


class FeedbackCreate(ApiBaseModel):
    action: str = Field(pattern="^(accepted|rejected|ignored)$")
    rating: str | None = Field(default=None, pattern="^(helpful|not_helpful|harmful)$")
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackRead(ApiBaseModel):
    id: str
    recommendation_id: str
    action: str
    rating: str | None
    incident_created: bool


class EvaluationMetricRead(ApiBaseModel):
    metric_name: str
    numerator: int
    denominator: int
    result: float | None


class EvaluationSummaryRead(ApiBaseModel):
    scope: str
    metrics: list[EvaluationMetricRead]
    incidents_open: int

