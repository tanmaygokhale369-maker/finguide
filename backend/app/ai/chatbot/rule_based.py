"""
Rule-based ChatbotEngine implementation.

Brick 06 scope: simple pattern matching over the incoming message, no
NLP/LLM. Replies are deliberately limited to greetings, small talk, and
an honest statement of current capabilities — this engine must never
generate financial advice, numbers, or claims, since no extraction,
validation, or safety/suitability pipeline exists yet for it to go
through (those arrive in Bricks 07-13). `history` is accepted to satisfy
the ChatbotEngine interface but this simple engine doesn't use it yet —
a future engine (rule-based or LLM) is free to.
"""

import re

from app.ai.chatbot.base import ChatbotEngine, ChatbotReply, ChatTurn, MarketContext

_GREETING_RE = re.compile(r"\b(hi|hello|hey|good morning|good evening|good afternoon)\b", re.IGNORECASE)
_THANKS_RE = re.compile(r"\b(thanks|thank you|thx)\b", re.IGNORECASE)
_FAREWELL_RE = re.compile(r"\b(bye|goodbye|see you|farewell)\b", re.IGNORECASE)
_HELP_RE = re.compile(r"\b(help|what can you do|capabilities)\b", re.IGNORECASE)

CAPABILITIES_MESSAGE = (
    "Right now I can chat and remember our conversation, but I can't yet analyze your "
    "finances, extract numbers from what you tell me, or make recommendations — those "
    "features are still being built. You can already set up your financial profile "
    "under Financial Profile."
)

FALLBACK_MESSAGE = (
    "I'm a simple rule-based assistant for now, so I can't fully understand that yet. "
    "I can say hello, tell you what I can currently do, or say goodbye — real financial "
    "understanding is on the way."
)


class RuleBasedChatbotEngine(ChatbotEngine):
    def generate_reply(self, history: list[ChatTurn], user_message: str, market_context: MarketContext | None = None) -> ChatbotReply:
        text = user_message.strip()

        if _HELP_RE.search(text):
            return ChatbotReply(content=CAPABILITIES_MESSAGE)
        if _THANKS_RE.search(text):
            return ChatbotReply(content="You're welcome! Let me know if there's anything else.")
        if _FAREWELL_RE.search(text):
            return ChatbotReply(content="Goodbye for now — come back anytime.")
        if _GREETING_RE.search(text):
            return ChatbotReply(
                content="Hi, I'm the FinGuide+ assistant. " + CAPABILITIES_MESSAGE
            )

        return ChatbotReply(content=FALLBACK_MESSAGE)
