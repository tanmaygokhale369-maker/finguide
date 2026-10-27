"""
Chat service.

Brick 06 scope: create/continue conversations, persist both sides of the
exchange, and call the configured ChatbotEngine with a bounded slice of
history. This is the one place that owns "conversation context is
controlled" — the engine never sees more than MAX_CONTEXT_MESSAGES turns,
and never sees another user's conversation.

Brick 07 addition: after persisting the user's message, financial-data
extraction runs on its text (see app/services/extraction_service.py).
Extraction never blocks or alters the chat reply — it only adds rows to
extracted_fields in the same transaction.
"""

import uuid

from sqlalchemy.orm import Session

from app.ai.chatbot import get_chatbot_engine
from app.ai.chatbot.base import ChatTurn
from app.core.config import settings
from app.models.conversation import Conversation
from app.models.feedback import ConsentRecord
from app.models.message import Message, MessageRole
from app.services import extraction_service
from app.services.chat_market_context import build_chat_market_context

# How many prior turns are fed to the engine as context. Bounded on
# purpose — see module docstring.
MAX_CONTEXT_MESSAGES = 20


class ConversationNotFoundError(Exception):
    pass


class AIProcessingConsentRequiredError(Exception):
    pass


def _get_owned_conversation(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if conversation is None:
        raise ConversationNotFoundError(f"No conversation {conversation_id} for this user")
    return conversation


def get_conversation_with_messages(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    return _get_owned_conversation(db, conversation_id, user_id)


def send_message(
    db: Session,
    user_id: uuid.UUID,
    message_text: str,
    conversation_id: uuid.UUID | None,
) -> tuple[Conversation, Message]:
    """
    Persist the user's message, run extraction on it, get a reply from
    the configured ChatbotEngine, persist the reply, and return
    (conversation, reply).

    If `conversation_id` is None, a new conversation is created. If it's
    provided but doesn't belong to this user (or doesn't exist), raises
    ConversationNotFoundError — the caller never gets to see or append to
    someone else's conversation.
    """
    provider = settings.chatbot_provider.lower()
    external_provider_ready = (
        (provider == "openai" and settings.openai_api_key and settings.openai_model)
        or (provider == "gemini" and settings.gemini_api_key and settings.gemini_model)
    )
    if external_provider_ready:
        required_policy_version = f"1.4-ai-{provider}-market-context" if provider == "gemini" else f"1.2-ai-{provider}"
        consent = (
            db.query(ConsentRecord)
            .filter(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == "ai_conversation_processing",
            )
            .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
            .first()
        )
        if (
            consent is None
            or not consent.granted
            or consent.policy_version != required_policy_version
        ):
            raise AIProcessingConsentRequiredError(
                "Enable AI conversation processing in Settings before sending chat messages to the configured provider."
            )

    if conversation_id is None:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.flush()  # assign conversation.id without ending the transaction
    else:
        conversation = _get_owned_conversation(db, conversation_id, user_id)

    prior_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(MAX_CONTEXT_MESSAGES)
        .all()
    )
    prior_messages.reverse()  # oldest first, as ChatbotEngine expects
    history = [ChatTurn(role=m.role, content=m.content) for m in prior_messages]

    user_message = Message(conversation_id=conversation.id, role=MessageRole.USER, content=message_text)
    db.add(user_message)
    db.flush()  # assign user_message.id so extraction rows can reference it

    extraction_service.extract_and_store(db, user_message, user_id)

    engine = get_chatbot_engine()
    market_context = (
        build_chat_market_context(message_text)
        if provider == "gemini" and external_provider_ready
        else None
    )
    reply = engine.generate_reply(
        history=history,
        user_message=message_text,
        market_context=market_context,
    )

    assistant_message = Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=reply.content)
    db.add(assistant_message)

    db.commit()
    db.refresh(assistant_message)
    db.refresh(conversation)
    # Search suggestions are response-only; do not write them to chat history.
    assistant_message.search_suggestions_html = reply.search_suggestions_html
    return conversation, assistant_message
