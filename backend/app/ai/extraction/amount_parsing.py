"""
Amount parsing for financial data extraction.

Handles the number formats FinGuide+'s own documented example uses
("5 lakh loan") as well as plain and comma-separated numbers, k/thousand,
and crore/million. This is intentionally a small, deterministic parser —
no NLP model — matching Brick 07's "regex-based extraction" scope.
"""

import re
from decimal import Decimal, InvalidOperation

_UNIT_MULTIPLIERS = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "lakh": Decimal(100_000),
    "lac": Decimal(100_000),
    "crore": Decimal(10_000_000),
    "cr": Decimal(10_000_000),
    "million": Decimal(1_000_000),
}

# Matches an optional currency marker, a number (with optional commas and
# decimal part), and an optional unit word — e.g. "₹65,000", "5 lakh",
# "2.5 crore", "60000".
AMOUNT_PATTERN = (
    r"(?:rs\.?|inr|₹|\$)?\s*"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)"
    r"\s*(?P<unit>k|thousand|lakh|lac|crore|cr|million)?"
)

_HEDGE_WORDS = (
    "around",
    "about",
    "approximately",
    "roughly",
    "nearly",
    "almost",
    "maybe",
    "~",
    "give or take",
)


def parse_amount(number_str: str, unit: str | None) -> Decimal | None:
    """Parses a matched number+unit into a Decimal amount, or None if the
    number portion isn't actually parseable (should be rare given the
    regex already constrains the format, but never silently guess)."""
    cleaned = number_str.replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None

    if unit:
        multiplier = _UNIT_MULTIPLIERS.get(unit.lower())
        if multiplier is not None:
            value = value * multiplier

    return value


def has_hedge_word(text: str, start: int, window: int = 20) -> bool:
    """Checks a short window of text before a match for hedging language
    ("around", "about", etc.), used to lower confidence and flag
    ambiguity rather than silently reporting a precise-looking number
    for what the user said was approximate."""
    preceding = text[max(0, start - window) : start].lower()
    return any(word in preceding for word in _HEDGE_WORDS)
