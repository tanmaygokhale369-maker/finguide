from pydantic import Field
from app.schemas.common import ApiBaseModel


class ConsentUpdate(ApiBaseModel):
    purpose: str = Field(pattern="^(financial_analysis|external_news_analysis|product_analytics|ai_conversation_processing)$")
    granted: bool
    policy_version: str = Field(min_length=1, max_length=30)


class DeleteAccountRequest(ApiBaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: bool
