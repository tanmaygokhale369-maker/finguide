"""
ValidationStatus — the six statuses required by the architecture docs
(Brick 08 — Data Validation & Confidence).

Not every status applies at every granularity:
- A single ExtractedField row (a concrete value that was actually
  extracted) can be VALID, LOW_CONFIDENCE, CONFLICTING, or REJECTED —
  never INCOMPLETE or REQUIRES_CLARIFICATION, since both of those
  describe the *absence* of a settled value, which contradicts a row
  existing with a concrete one.
- A field-level summary (across all of a user's history for one field
  name — see app/services/validation_service.py) can be any of the six,
  including INCOMPLETE (no data at all) and REQUIRES_CLARIFICATION (data
  exists but conflicts, so the recommended next action is to ask).
"""

import enum


class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CONFLICTING = "CONFLICTING"
    INCOMPLETE = "INCOMPLETE"
    REQUIRES_CLARIFICATION = "REQUIRES_CLARIFICATION"
    REJECTED = "REJECTED"
