"""
Explainability — Brick 14.

Builds the per-recommendation explanation answering the seven questions
the Implementation Plan's Brick 14 section requires:

1. What is being recommended?            -> title / category
2. Why is it relevant?                   -> reason (Brick 12)
3. Which user data influenced it?        -> based_on, resolved against the
                                             actual DerivedMetric row
                                             (Brick 09): formula,
                                             input_values, calculated_at
4. Which external evidence influenced it?-> source_references (always []
                                             today — no verified external
                                             provider is configured
5. What assumptions were made?           -> the deterministic rule's
                                             documented threshold (see
                                             RULE_ASSUMPTIONS, mirroring
                                             the constants in
                                             recommendation_service.py)
                                             plus any metric-level
                                             missing_inputs
6. How confident is the system?          -> confidence, with an explicit
                                             note that this is a
                                             deterministic threshold rule,
                                             not a probabilistic/ML score
                                             (SHAP/LIME don't apply — no
                                             model exists to explain)
7. What limitations exist?               -> Brick 13's safety_checks /
                                             safety_explanation, plus
                                             structural limitations (no
                                             verified external evidence yet; not
                                             yet safety-reviewed if still
                                             CANDIDATE; debt-category's
                                             known missing-field gap)

This brick builds no new stored data. Per the Implementation Plan,
Brick 14's job is to make already-captured reasoning visible and
traceable, not to capture new reasoning — every field below is
assembled from Recommendation (Brick 12/13) and DerivedMetric (Brick 09)
rows that already exist.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.derived_metric import DerivedMetric
from app.models.recommendation import RecommendationCategory, RecommendationState
from app.services.recommendation_service import RecommendationNotFoundError, get_recommendation

# Mirrors the threshold constants in recommendation_service.py, in prose
# form — this is explanation text for a person, not a value to compare
# against, so it's kept separate rather than importing the raw Decimals.
RULE_ASSUMPTIONS = {
    "emergency_fund_low_coverage": (
        "Uses the standard personal-finance guideline of 3 months' expenses "
        "as a minimum emergency fund."
    ),
    "high_expense_to_income_ratio": (
        "Uses 90% of income as the threshold for 'little margin' in monthly expenses."
    ),
    "low_savings_ratio": (
        "Uses 10% of income as the commonly recommended minimum savings rate."
    ),
    "high_debt_to_income_ratio": (
        "Uses 6 months' worth of income as the threshold for an elevated total "
        "debt balance. This is balance-based, not a standard payment-based "
        "debt-to-income ratio — see Brick 09's documented caveat on this metric."
    ),
}


@dataclass
class UserDataUsed:
    metric_name: str | None
    metric_value: str | None
    formula: str | None
    input_values: dict
    calculation_version: str | None
    calculated_at: str | None


@dataclass
class Explanation:
    recommendation_id: uuid.UUID
    what: str
    why: str
    user_data_used: UserDataUsed | None
    external_evidence: list
    assumptions: list[str] = field(default_factory=list)
    confidence: str = ""
    confidence_note: str = ""
    limitations: list[str] = field(default_factory=list)


def build_explanation(db: Session, user_id: uuid.UUID, recommendation_id: uuid.UUID) -> Explanation:
    rec = get_recommendation(db, user_id, recommendation_id)

    metric_id = rec.based_on.get("derived_metric_id")
    metric = db.query(DerivedMetric).filter(DerivedMetric.id == metric_id, DerivedMetric.user_id == user_id).first() if metric_id else None

    user_data_used = None
    if metric is not None:
        user_data_used = UserDataUsed(
            metric_name=metric.metric_name,
            metric_value=str(metric.value) if metric.value is not None else None,
            formula=metric.formula,
            input_values=metric.input_values,
            calculation_version=metric.calculation_version,
            calculated_at=metric.calculated_at.isoformat(),
        )

    assumptions: list[str] = []
    rule_assumption = RULE_ASSUMPTIONS.get(rec.rule_id)
    if rule_assumption:
        assumptions.append(rule_assumption)
    if metric is not None and metric.missing_inputs:
        assumptions.append(f"Computed with these inputs marked missing at the time: {metric.missing_inputs}.")

    limitations: list[str] = []
    if rec.state == RecommendationState.CANDIDATE:
        limitations.append("This recommendation has not yet passed the Brick 13 safety/suitability review.")
    else:
        for check in rec.safety_checks:
            if not check.get("passed", True):
                limitations.append(f"Safety check '{check['check']}' did not pass: {check['detail']}")

    if not rec.source_references:
        limitations.append(
            "No external evidence sources were used — this recommendation is based "
            "solely on the user's own computed financial data. External evidence "
            "submission exists, but no trusted provider is configured; user-submitted "
            "evidence remains unverified and is not used to support recommendations."
        )
    if rec.category == RecommendationCategory.DEBT:
        limitations.append(
            "Based on total debt balance only — the system does not currently capture "
            "monthly repayment/EMI obligations, which would give a more precise picture."
        )

    return Explanation(
        recommendation_id=rec.id,
        what=f"{rec.title} (category: {rec.category.value})",
        why=rec.reason,
        user_data_used=user_data_used,
        external_evidence=rec.source_references,
        assumptions=assumptions,
        confidence=str(rec.confidence),
        confidence_note=(
            "This is a deterministic threshold rule, not a probabilistic model score — "
            "it either fires or it doesn't, so confidence is always 1.00. SHAP/LIME-style "
            "explanation methods don't apply here since there is no statistical model "
            "behind this candidate."
        ),
        limitations=limitations,
    )


__all__ = ["build_explanation", "Explanation", "UserDataUsed", "RecommendationNotFoundError"]
