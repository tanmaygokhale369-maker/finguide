"""
Conversation model.

Brick 06 scope: DB structure for the chatbot's server-controlled
conversation state. A user may have multiple conversations; each
conversation owns an ordered list of Messages.
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
