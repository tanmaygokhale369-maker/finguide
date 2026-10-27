"""
Extraction service.

Brick 07 scope: run the configured FinancialExtractionEngine over a
message's text and persist every candidate it returns. This never
writes to FinancialProfile — see the module docstring on
app/models/extracted_field.py.

Brick 08 addition: after persisting new candidates, revalidate every
field_name touched by this message. Revalidation looks at that field's
*entire* history for this user, not just the new rows, so a value
mentioned today can correctly turn an old row CONFLICTING.
"""

import uuid

from sqlalchemy.orm import Session

from app.ai.extraction import get_extraction_engine
from app.models.conversation import Conversation
from app.models.extracted_field import ExtractedField
from app.models.message import Message
from app.services.validation_service import revalidate_field


class ConversationNotFoundError(Exception):
    pass


def extract_and_store(db: Session, message: Message, user_id: uuid.UUID) -> list[ExtractedField]:
    """
    Runs extraction on `message.content`, persists one ExtractedField row
    per candidate found, and revalidates every field_name touched. Does
    not commit — the caller (chat_service) commits as part of its own
    transaction, so a failed reply generation doesn't leave orphaned
    extraction rows.
    """
    engine = get_extraction_engine()
    candidates = engine.extract(message.content)

    rows = []
    touched_field_names: set[str] = set()
    for candidate in candidates:
        row = ExtractedField(
            message_id=message.id,
            user_id=user_id,
            field_name=candidate.field_name,
            value=candidate.value,
            source_text=candidate.source_text,
            confidence=candidate.confidence,
            extraction_method=candidate.extraction_method,
            is_ambiguous=candidate.is_ambiguous,
            ambiguity_reason=candidate.ambiguity_reason,
        )
        db.add(row)
        rows.append(row)
        touched_field_names.add(candidate.field_name)

    if touched_field_names:
        db.flush()  # new rows need ids/visibility before revalidate_field queries them
        for field_name in touched_field_names:
            revalidate_field(db, user_id, field_name)

    return rows


def list_extractions_for_conversation(
    db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> list[ExtractedField]:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if conversation is None:
        raise ConversationNotFoundError(f"No conversation {conversation_id} for this user")

    return (
        db.query(ExtractedField)
        .join(Message, ExtractedField.message_id == Message.id)
        .filter(Message.conversation_id == conversation_id)
        .order_by(ExtractedField.created_at)
        .all()
    )
