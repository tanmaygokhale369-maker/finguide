"""
Chatbot engine factory.

The chat service depends only on `get_chatbot_engine()` and the
`ChatbotEngine` interface. The provider is selected by backend
configuration; API and persistence layers do not depend on a vendor.
"""

from app.ai.chatbot.base import ChatbotEngine
from app.ai.chatbot.rule_based import RuleBasedChatbotEngine
from app.core.config import settings

_engine: ChatbotEngine | None = None


def get_chatbot_engine() -> ChatbotEngine:
    global _engine
    if _engine is None:
        provider = settings.chatbot_provider.lower()
        if provider == "openai":
            from app.ai.chatbot.openai_engine import OpenAIChatbotEngine

            _engine = OpenAIChatbotEngine()
        elif provider == "gemini":
            from app.ai.chatbot.gemini_engine import GeminiChatbotEngine

            _engine = GeminiChatbotEngine()
        else:
            _engine = RuleBasedChatbotEngine()
    return _engine
