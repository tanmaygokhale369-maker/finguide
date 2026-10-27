# FinGuide+ — Financial Data Validation & Context Specification

## Purpose
Prevent incorrect or incomplete extracted data from silently influencing recommendations.

## Data Lifecycle

```text
Raw User Text
→ Extraction
→ Normalization
→ Confidence Score
→ Validation
→ Contradiction Detection
→ Context Completeness
→ Approved Financial State
```

## Confidence

Each extracted field should support:
- value
- confidence
- extraction method
- source text/span
- validation state

Example:

```json
{
  "monthly_income": {
    "value": 65000,
    "confidence": 0.94,
    "source": "I earn around 65k per month",
    "status": "validated"
  }
}
```

## Contradiction Detection

Examples:
- User says monthly income is ₹50,000 and later says ₹80,000.
- User says they have no debt and later reports an EMI.
- Expense totals exceed income without an explanation.

Do not silently overwrite. Ask for clarification or retain version history.

## Missing Context

Critical context should be represented explicitly:

```text
KNOWN
UNKNOWN
AMBIGUOUS
CONFLICTING
NOT_APPLICABLE
```

## Minimum Context Before Personalized Recommendations

The required fields depend on recommendation type.

For example:
- budgeting → income + essential expenses + spending
- debt-related guidance → debt + income + repayment obligations
- investment-related guidance → goal + horizon + liquidity needs + risk information + relevant existing financial context

The system must use a recommendation-specific context policy rather than one universal checklist.

## Validation Outcomes

- `VALID`
- `LOW_CONFIDENCE`
- `CONFLICTING`
- `INCOMPLETE`
- `REQUIRES_CLARIFICATION`
- `REJECTED`

## Principle

> Uncertainty in financial data must propagate into recommendation confidence rather than disappearing during processing.
