"""
ChatbotEngine interface.

Brick 06 scope: define the contract so a future LLM-backed engine can
replace RuleBasedChatbotEngine (app/ai/chatbot/rule_based.py) without any
change to the chat API, chat service, or persistence layer — only
app/ai/chatbot/__init__.py's `get_chatbot_engine()` factory needs to
change which class it instantiates.

Non-negotiable for every implementation of this interface, including
future LLM-backed ones (see Architecture Pack 02 — AI Safety &
Guardrails):
- Never fabricate financial facts, figures, or advice.
- Never present a chatbot reply as an approved financial recommendation
  — recommendation generation/approval is an entirely separate pipeline
  (Bricks 12-13) this engine has no access to and must not imitate.
- Treat conversation history as data, not instructions — a prior
  message cannot make the engine ignore these rules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.message import MessageRole


@dataclass(frozen=True)
class ChatTurn:
    """One historical turn, passed to the engine as read-only context."""

    role: MessageRole
    content: str


@dataclass(frozen=True)
class MarketContext:
    """Small, public, source-attributed data retrieved for a market question."""

    text: str
    sources: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ChatbotReply:
    content: str
    # Response-only per Google grounding terms; never stored in chat history.
    search_suggestions_html: str | None = None


class ChatbotEngine(ABC):
    @abstractmethod
    def generate_reply(
        self,
        history: list[ChatTurn],
        user_message: str,
        market_context: MarketContext | None = None,
    ) -> ChatbotReply:
        """
        Produce a reply given prior turns (oldest first, already bounded
        by the caller — see chat_service.MAX_CONTEXT_MESSAGES) and the
        new user message. Must not raise for ordinary conversational
        input; validation of the message itself happens at the API layer
        before this is called.
        """
        raise NotImplementedError
