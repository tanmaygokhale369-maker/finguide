"""
Financial extraction engine factory.

The extraction service depends only on `get_extraction_engine()` and the
`FinancialExtractionEngine` interface — never on
`RegexFinancialExtractionEngine` directly. Swapping in a future ML/LLM
extractor means changing only this function's body.
"""

from app.ai.extraction.base import FinancialExtractionEngine
from app.ai.extraction.regex_engine import RegexFinancialExtractionEngine

_engine: FinancialExtractionEngine = RegexFinancialExtractionEngine()


def get_extraction_engine() -> FinancialExtractionEngine:
    return _engine
