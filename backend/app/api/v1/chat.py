"""
Chat endpoints.

Like the profile endpoints, identity comes from `get_current_user` —
never a client-supplied user_id. A conversation belongs to exactly the
user who owns it; requesting another user's conversation_id behaves
identically to it not existing (404), so existence isn't leaked either.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ConversationRead, MessageRead
from app.schemas.extraction import ExtractedFieldRead
from app.services import chat_service, extraction_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/capabilities")
def get_chat_capabilities():
    provider = settings.chatbot_provider.lower()
    if provider == "openai":
        ready = bool(settings.openai_api_key and settings.openai_model)
        provider_name = "OpenAI"
    elif provider == "gemini":
        ready = bool(settings.gemini_api_key and settings.gemini_model)
        provider_name = "Gemini"
    else:
        ready = True
        provider_name = "rule-based"
    return {
        "provider": provider_name,
        "ready": ready,
        "requires_ai_consent": provider in {"openai", "gemini"} and ready,
        "consent_policy_version": "1.4-ai-gemini-market-context" if provider == "gemini" else "1.2-ai-openai" if provider == "openai" else None,
    }


def _parse_conversation_id(conversation_id: str) -> _uuid.UUID:
    try:
        return _uuid.UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="conversation_id must be a UUID") from exc


@router.post("", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    try:
        conversation, reply = chat_service.send_message(
            db,
            user_id=current_user.id,
            message_text=payload.message,
            conversation_id=payload.conversation_id,
        )
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except chat_service.AIProcessingConsentRequiredError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    reply_read = MessageRead.model_validate(reply).model_copy(
        update={"search_suggestions_html": getattr(reply, "search_suggestions_html", None)}
    )
    return ChatMessageResponse(conversation_id=conversation.id, reply=reply_read)


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationRead:
    parsed_id = _parse_conversation_id(conversation_id)

    try:
        conversation = chat_service.get_conversation_with_messages(db, parsed_id, current_user.id)
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ConversationRead.model_validate(conversation)


@router.get("/{conversation_id}/extractions", response_model=list[ExtractedFieldRead])
def get_extractions(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExtractedFieldRead]:
    parsed_id = _parse_conversation_id(conversation_id)

    try:
        rows = extraction_service.list_extractions_for_conversation(db, parsed_id, current_user.id)
    except extraction_service.ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [ExtractedFieldRead.model_validate(row) for row in rows]
