"""
Chat schemas.

Brick 06 scope: plain conversational request/response shapes. No
extracted-data or recommendation fields here — those belong to the
schemas Bricks 07 and 12 introduce for their own endpoints.
"""

import uuid
from datetime import datetime

from pydantic import Field

from app.models.message import MessageRole
from app.schemas.common import ApiBaseModel


class ChatMessageRequest(ApiBaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class MessageRead(ApiBaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    search_suggestions_html: str | None = None


class ChatMessageResponse(ApiBaseModel):
    conversation_id: uuid.UUID
    reply: MessageRead


class ConversationRead(ApiBaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead]
