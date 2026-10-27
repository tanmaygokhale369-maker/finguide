"""
FinancialExtractionEngine interface.

Brick 07 scope: define the contract so a future ML/LLM-backed extractor
can replace RegexFinancialExtractionEngine without changing the service,
persistence, or API layer — only app/ai/extraction/__init__.py's factory
needs to change.

Non-negotiable for every implementation (see Architecture v1.1 LOCK and
Architecture Pack 04 — Data Validation & Context):
- Never invent a value that isn't actually present in the text.
- If a field can't be confidently extracted, omit it — do not guess.
- If the same field is mentioned more than once with different values,
  return a candidate for each occurrence rather than silently picking
  one, and mark each with `is_ambiguous=True` — resolving contradictions
  is Brick 08's job (Data Validation & Confidence), not the extractor's,
  but the extractor must never hide that a contradiction exists.
- A weak or uncertain match (e.g. a number paired with a keyword only
  because it's the nearest one, not because the phrasing is clear) must
  also set `is_ambiguous=True` with a human-readable `ambiguity_reason`
  — lowering confidence alone is not sufficient flagging.
- Extracted values are candidates, not approved financial data — nothing
  here writes to FinancialProfile directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ExtractedFieldCandidate:
    field_name: str
    value: Decimal
    source_text: str
    confidence: Decimal
    extraction_method: str
    is_ambiguous: bool = False
    ambiguity_reason: str | None = None


class FinancialExtractionEngine(ABC):
    @abstractmethod
    def extract(self, text: str) -> list[ExtractedFieldCandidate]:
        """Return zero or more candidates found in `text`. Must not raise
        for ordinary conversational input — an engine that finds nothing
        simply returns an empty list."""
        raise NotImplementedError
