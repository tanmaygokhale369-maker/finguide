from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pydantic import AnyHttpUrl, Field, model_validator

from app.schemas.common import ApiBaseModel


class EvidenceCreate(ApiBaseModel):
    source_name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(pattern="^(market|economic|news|web|social|reference)$")
    source_url: AnyHttpUrl
    retrieved_at: datetime
    published_at: datetime | None = None
    valid_until: datetime | None = None
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20000)
    relevance: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_timestamps(self):
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone.")
        if self.retrieved_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("retrieved_at cannot be in the future.")
        if self.published_at and self.published_at.tzinfo is None:
            raise ValueError("published_at must include a timezone.")
        if self.valid_until and self.valid_until.tzinfo is None:
            raise ValueError("valid_until must include a timezone.")
        if self.valid_until and self.valid_until <= self.retrieved_at:
            raise ValueError("valid_until must be later than retrieved_at.")
        if self.published_at and self.published_at > self.retrieved_at:
            raise ValueError("published_at cannot be later than retrieved_at.")
        if self.source_url.scheme != "https":
            raise ValueError("source_url must use HTTPS.")
        if self.source_url.username or self.source_url.password:
            raise ValueError("source_url must not contain embedded credentials.")
        return self


class EvidenceRead(ApiBaseModel):
    id: str
    source_name: str
    source_type: str
    source_url: str
    retrieved_at: datetime
    published_at: datetime | None
    valid_until: datetime | None
    credibility: Decimal
    content_hash: str
    title: str
    relevance: str | None
    verification_status: str
    freshness_status: str
    conflict_metadata: dict
    sentiment_label: str
    sentiment_confidence: Decimal | None
    sentiment_model: str | None
