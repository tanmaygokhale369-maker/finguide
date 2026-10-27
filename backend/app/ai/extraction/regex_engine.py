"""
Regex-based FinancialExtractionEngine implementation.

Brick 07 scope: no NLP/LLM — this finds numbers in the text (handling
Indian numbering: "lakh"/"crore"/"k" suffixes and comma grouping) and
pairs each with the nearest recognized keyword for a known field. A
close keyword-number pairing gets high confidence; a farther, weaker
pairing gets reduced confidence, which is this engine's way of "flagging
ambiguity" — Brick 08 is responsible for turning low confidence into an
actual clarification request.

Fields extracted here mirror FinancialProfile's simplest, most
extractable columns: monthly_income, monthly_expenses, debt, savings,
dependents. Fields that need more nuance than "a number near a keyword"
(insurance, risk preference, goals) are left for a smarter engine or
direct profile entry — see FinancialExtractionEngine's docstring on not
guessing.
"""

import re
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from app.ai.extraction.base import ExtractedFieldCandidate, FinancialExtractionEngine

EXTRACTION_METHOD = "regex_v1"

# A number: digit groups with optional commas and a decimal part, e.g.
# "60000", "60,000", "1.5", followed by an optional Indian/English scale
# word. Comma grouping isn't validated strictly (e.g. "6,0000" still
# parses) since we only need the numeric value, not to validate the
# user's formatting.
_NUMBER_RE = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>lakhs?|crores?|k\b)?",
    re.IGNORECASE,
)

_SCALE_MULTIPLIERS = {
    "lakh": Decimal(100_000),
    "lakhs": Decimal(100_000),
    "crore": Decimal(10_000_000),
    "crores": Decimal(10_000_000),
    "k": Decimal(1_000),
}

# (field_name, keyword pattern, base confidence when the match is close)
_FIELD_KEYWORDS: list[tuple[str, re.Pattern, Decimal]] = [
    ("monthly_income", re.compile(r"\b(earn(?:s|ing)?|income|salary)\b", re.IGNORECASE), Decimal("0.90")),
    ("monthly_expenses", re.compile(r"\b(spend(?:s|ing)?|expenses?)\b", re.IGNORECASE), Decimal("0.90")),
    ("debt", re.compile(r"\b(debt|loan|owe|emi)\b", re.IGNORECASE), Decimal("0.90")),
    ("savings", re.compile(r"\b(savings?|saved)\b", re.IGNORECASE), Decimal("0.85")),
    ("dependents", re.compile(r"\b(dependents?|kids?|children)\b", re.IGNORECASE), Decimal("0.80")),
]

# Keyword-to-number windows within this many characters count as a
# close/confident pairing; beyond that (up to _MAX_WINDOW) is treated as
# a weaker, lower-confidence pairing; beyond _MAX_WINDOW, not paired.
_CLOSE_WINDOW = 15
_MAX_WINDOW = 30
_WEAK_CONFIDENCE_FACTOR = Decimal("0.6")


class _NumberMatch:
    __slots__ = ("value", "source_text", "start", "end")

    def __init__(self, value: Decimal, source_text: str, start: int, end: int):
        self.value = value
        self.source_text = source_text
        self.start = start
        self.end = end


def _parse_numbers(text: str) -> list[_NumberMatch]:
    results = []
    for match in _NUMBER_RE.finditer(text):
        raw_num = match.group("num")
        suffix = (match.group("suffix") or "").lower()
        try:
            value = Decimal(raw_num.replace(",", ""))
        except InvalidOperation:
            continue
        if suffix:
            value *= _SCALE_MULTIPLIERS[suffix]
        if value < 0:
            continue
        results.append(_NumberMatch(value=value, source_text=match.group(0).strip(), start=match.start(), end=match.end()))
    return results


def _distance(keyword_start: int, keyword_end: int, number: _NumberMatch) -> int:
    if number.start >= keyword_end:
        return number.start - keyword_end
    if number.end <= keyword_start:
        return keyword_start - number.end
    return 0  # overlapping (shouldn't normally happen)


class RegexFinancialExtractionEngine(FinancialExtractionEngine):
    def extract(self, text: str) -> list[ExtractedFieldCandidate]:
        numbers = _parse_numbers(text)
        if not numbers:
            return []

        candidates: list[ExtractedFieldCandidate] = []
        for field_name, keyword_re, base_confidence in _FIELD_KEYWORDS:
            for kw_match in keyword_re.finditer(text):
                best = None
                best_distance = None
                for number in numbers:
                    distance = _distance(kw_match.start(), kw_match.end(), number)
                    if distance > _MAX_WINDOW:
                        continue
                    if best_distance is None or distance < best_distance:
                        best, best_distance = number, distance

                if best is None:
                    continue

                confidence = base_confidence
                is_ambiguous = False
                ambiguity_reason = None
                if best_distance > _CLOSE_WINDOW:
                    confidence = (confidence * _WEAK_CONFIDENCE_FACTOR).quantize(Decimal("0.01"))
                    is_ambiguous = True
                    ambiguity_reason = (
                        f"the matched number is {best_distance} characters from the "
                        f"'{field_name}' keyword, not an adjacent, clear pairing"
                    )

                candidates.append(
                    ExtractedFieldCandidate(
                        field_name=field_name,
                        value=best.value,
                        source_text=best.source_text,
                        confidence=confidence,
                        extraction_method=EXTRACTION_METHOD,
                        is_ambiguous=is_ambiguous,
                        ambiguity_reason=ambiguity_reason,
                    )
                )

        return _flag_conflicting_values(candidates)


def _flag_conflicting_values(candidates: list[ExtractedFieldCandidate]) -> list[ExtractedFieldCandidate]:
    """
    If the same field has more than one distinct value among this
    message's candidates, every candidate for that field is marked
    ambiguous — the message itself contains a contradiction (or at least
    two plausible readings), and that must be visible to whatever
    consumes these candidates, not silently resolved by picking one.
    """
    values_by_field: dict[str, set[Decimal]] = {}
    for candidate in candidates:
        values_by_field.setdefault(candidate.field_name, set()).add(candidate.value)

    conflicted_fields = {field for field, values in values_by_field.items() if len(values) > 1}
    if not conflicted_fields:
        return candidates

    result = []
    for candidate in candidates:
        if candidate.field_name in conflicted_fields and not candidate.is_ambiguous:
            candidate = replace(
                candidate,
                is_ambiguous=True,
                ambiguity_reason=(
                    f"multiple differing values were mentioned for '{candidate.field_name}' in this message"
                ),
            )
        result.append(candidate)
    return result
