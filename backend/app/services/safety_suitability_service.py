"""
Safety & Suitability Layer — Brick 13.

The mandatory gate between candidate generation (Brick 12) and anything
resembling a user-facing recommendation, per Architecture v1.1 LOCK's
non-negotiable constraint #1 ("AI generation never directly becomes the
final user-facing financial recommendation") and the canonical
pipeline's "Suitability Validation -> Safety & Policy Gate" stage.

VOCABULARY RECONCILIATION (read this before touching this file):
Two architecture docs define overlapping-but-different vocabularies for
this layer, and this brick resolves the conflict explicitly rather than
silently picking one — per the Implementation Plan's instruction to
explain conflicts between documentation and existing code:

- Pack 02 ("AI Safety & Guardrails Specification") defines SIX safety
  DECISIONS: APPROVE, CLARIFY, EDUCATE, LIMIT, BLOCK, ESCALATE.
- The Implementation Plan's "Recommendation lifecycle" (already migrated
  into `recommendations.state` back in Brick 12) is: CANDIDATE ->
  VALIDATED -> APPROVED / MODIFIED / BLOCKED / CLARIFY / ESCALATE ->
  PRESENTED -> ACCEPTED / REJECTED / IGNORED -> EVALUATED. That list has
  no EDUCATE or LIMIT value.

Altering the already-migrated `recommendation_state` enum to shoehorn in
two more values felt like the wrong fix for what is fundamentally a
vocabulary mismatch, not a missing capability. Instead:
  - `state` gets the matching lifecycle value: APPROVE->APPROVED,
    BLOCK->BLOCKED, CLARIFY->CLARIFY, ESCALATE->ESCALATE, and both
    EDUCATE and LIMIT -> MODIFIED (the candidate is not being shown to a
    user as originally generated, which is what MODIFIED means here).
  - `suitability_status` (added nullable in Brick 12 specifically for
    this brick to fill in) gets the EXACT Pack 02 decision string
    ("APPROVE"/"CLARIFY"/"EDUCATE"/"LIMIT"/"BLOCK"/"ESCALATE") — this is
    the field to read if you need to know precisely which of the six
    outcomes occurred, not `state`.

Presentation and feedback lifecycle transitions are handled by the
recommendation and feedback APIs; this gate only validates candidates.

WHAT'S ACTUALLY CHECKED, and why (mapped against Pack 02's "Mandatory
Checks" and the Recommendation Policy's "Suitability Rules"):

1. Staleness (Rule 6 — freshness). A candidate's `based_on.computation_id`
   must match the user's CURRENT latest derived-metrics computation. If
   the user's profile has been recomputed since this candidate was
   generated, the candidate is reasoning from numbers that may no longer
   be true -> BLOCK.

2. Policy version (Rule 7 — versioning). If a candidate was generated
   under a policy_version this validator doesn't recognize as current,
   it needs human review rather than an automatic decision -> ESCALATE.

3. Forbidden language (Output Safety: "avoid claiming guaranteed
   returns" / "avoid fabricated facts"). Every candidate's title/reason
   is scanned for a fixed list of banned phrases. This can never
   actually fire against Brick 12's own fixed templates today — it's
   defense-in-depth for when an LLM-based generator exists (a future
   brick) and might produce free text that needs this exact guard.

4. Category-specific context completeness (Recommendation Policy's
   Suitability Rules + Pack 04's minimum-context-by-type: "debt-related
   guidance -> debt + income + repayment obligations"). FinancialProfile
   (Brick 04/05) has no field for monthly repayment/EMI obligations —
   only a total debt balance. For DEBT-category candidates this is a
   genuinely missing required input, not a borderline judgment call ->
   CLARIFY, asking for the missing detail rather than guessing.

5. Risk override: any candidate with risk_level=HIGH is escalated
   regardless of category, since no current rule in Brick 12 produces
   HIGH (all four rules are LOW/MEDIUM) — this exists so the check
   pipeline is already correct the day a HIGH-risk rule is added, rather
   than silently defaulting it to APPROVE.

6. Category-based default: BUDGETING candidates are, as currently
   worded ("Review your monthly budget"), general guidance rather than a
   specific personalized action — this matches Pack 02's own definition
   of EDUCATE ("general financial education without personalized
   action") -> EDUCATE. EMERGENCY_FUND and SAVINGS candidates are
   concrete, actionable, LOW risk, and have passed every check above ->
   APPROVE.

WHAT'S DELIBERATELY NOT CHECKED, and why (so this isn't mistaken for an
oversight):

- "Conflicts with the user's stated goal" (Suitability Rules). 
  FinancialProfile.financial_goals is unstructured free text (Brick
  04/05) — determining whether a candidate "conflicts" with free text
  requires either structured goal data (doesn't exist) or NLP/LLM
  interpretation (out of scope for this deterministic brick, and would
  reintroduce exactly the "AI as final authority" risk this whole layer
  exists to prevent). Not implemented; flagged as a known gap.
- "Missing evidence" (Suitability Rules) is not a blocking check here.
  Current candidates have no source_references because no verified
  external provider is configured; user-submitted evidence remains
  unverified — but these
  candidates make no claim that requires external corroboration (market
  rates, news, predictions); they're statements about the user's own
  computed ratios. Blocking on an evidence requirement that doesn't
  apply to this content would be checking a box, not providing safety.
- "User contradiction" (Pack 02 Input Safety) is Brick 08's concern
  (chat-extracted data) and doesn't apply to FinancialProfile, which is
  explicit user-confirmed data with no "contradiction" concept at this
  layer (Brick 05).
- Fact/Grounding Verification (a named canonical-pipeline stage) checks
  deterministic candidate data and policy results. Unverified external
  evidence is not used, and no free-text generation (no LLM) exists.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.feedback import RecommendationAuditEvent
from app.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationRiskLevel,
    RecommendationState,
)
from app.services import metrics_service

# This validator's own notion of "current" policy — compared against
# each candidate's recommendation.policy_version (set by Brick 12).
CURRENT_POLICY_VERSION = "v1"

# Defense-in-depth output-safety scan — see check #3 in the module
# docstring. Matched case-insensitively as a substring of title+reason.
_FORBIDDEN_PHRASES = [
    "guaranteed",
    "guarantee",
    "risk-free",
    "risk free",
    "100% safe",
    "no risk",
    "sure thing",
    "cannot lose",
    "can't lose",
]


class RecommendationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class CheckResult:
    check: str
    passed: bool
    detail: str


@dataclass
class EvaluationResult:
    recommendation_id: uuid.UUID
    decision: str  # APPROVE | CLARIFY | EDUCATE | LIMIT | BLOCK | ESCALATE
    state: RecommendationState
    explanation: str
    checks: list[CheckResult] = field(default_factory=list)


def _check_staleness(db: Session, rec: Recommendation) -> CheckResult:
    latest = metrics_service.get_latest_computation(db, rec.user_id)
    current_computation_id = str(latest[0]) if latest is not None else None
    candidate_computation_id = rec.based_on.get("computation_id")

    if current_computation_id is None or candidate_computation_id != current_computation_id:
        return CheckResult(
            "staleness",
            False,
            "The user's financial metrics have been recomputed since this "
            "candidate was generated; the numbers it cites may no longer be current.",
        )
    return CheckResult("staleness", True, "Candidate reflects the user's current computed metrics.")


def _check_policy_version(rec: Recommendation) -> CheckResult:
    if rec.policy_version != CURRENT_POLICY_VERSION:
        return CheckResult(
            "policy_version",
            False,
            f"Candidate was generated under policy_version={rec.policy_version!r}, "
            f"expected {CURRENT_POLICY_VERSION!r}.",
        )
    return CheckResult("policy_version", True, "Candidate matches the current policy version.")


def _check_forbidden_language(rec: Recommendation) -> CheckResult:
    text = f"{rec.title} {rec.reason}".lower()
    hits = [phrase for phrase in _FORBIDDEN_PHRASES if phrase in text]
    if hits:
        return CheckResult("forbidden_language", False, f"Found banned phrase(s): {hits}.")
    return CheckResult("forbidden_language", True, "No banned phrases found.")


def _check_context_completeness(rec: Recommendation) -> CheckResult:
    if rec.category == RecommendationCategory.DEBT:
        return CheckResult(
            "context_completeness",
            False,
            "Debt-related guidance requires monthly repayment-obligation data, "
            "which FinancialProfile does not currently capture (only a total "
            "debt balance) — see Pack 04's minimum-context-by-type policy.",
        )
    return CheckResult("context_completeness", True, "Required context for this category is present.")


def evaluate_candidate(db: Session, rec: Recommendation) -> EvaluationResult:
    """
    Runs every check against one CANDIDATE-state Recommendation and
    persists the outcome (state, suitability_status, safety_explanation,
    safety_checks). Idempotent in effect — re-evaluating a row that has
    already moved past CANDIDATE just re-runs the same deterministic
    checks and overwrites the same conclusion, since nothing here is
    randomized; it is not re-filtered to CANDIDATE-only by this function
    itself (the API layer controls which rows get evaluated — see
    evaluate_pending_candidates).
    """
    previous_state = rec.state.value
    checks = [
        _check_staleness(db, rec),
        _check_policy_version(rec),
        _check_forbidden_language(rec),
        _check_context_completeness(rec),
    ]

    failed = {c.check: c for c in checks if not c.passed}

    if "staleness" in failed:
        decision, state, explanation = "BLOCK", RecommendationState.BLOCKED, failed["staleness"].detail
    elif "policy_version" in failed:
        decision, state, explanation = "ESCALATE", RecommendationState.ESCALATE, failed["policy_version"].detail
    elif "forbidden_language" in failed:
        decision, state, explanation = "BLOCK", RecommendationState.BLOCKED, failed["forbidden_language"].detail
    elif "context_completeness" in failed:
        decision, state, explanation = "CLARIFY", RecommendationState.CLARIFY, failed["context_completeness"].detail
    elif rec.risk_level == RecommendationRiskLevel.HIGH:
        decision, state = "ESCALATE", RecommendationState.ESCALATE
        explanation = "High risk_level candidates require human escalation regardless of category."
    elif rec.category == RecommendationCategory.BUDGETING:
        decision, state = "EDUCATE", RecommendationState.MODIFIED
        explanation = "Budgeting guidance at this stage is general education, not a specific personalized action."
    else:
        decision, state = "APPROVE", RecommendationState.APPROVED
        explanation = "All checks passed; candidate is concrete, actionable, and low risk."

    rec.state = state
    rec.suitability_status = decision
    rec.safety_explanation = explanation
    rec.safety_checks = [{"check": c.check, "passed": c.passed, "detail": c.detail} for c in checks]
    db.add(rec)
    if previous_state != state.value:
        if not failed:
            db.add(RecommendationAuditEvent(
                user_id=rec.user_id,
                recommendation_id=rec.id,
                from_state=previous_state,
                to_state=RecommendationState.VALIDATED.value,
                event_type="candidate_validated",
                metadata_json={"checks_passed": [c.check for c in checks], "policy_version": CURRENT_POLICY_VERSION},
            ))
        db.add(RecommendationAuditEvent(
            user_id=rec.user_id,
            recommendation_id=rec.id,
            from_state=RecommendationState.VALIDATED.value if not failed else previous_state,
            to_state=state.value,
            event_type="safety_evaluation",
            metadata_json={"decision": decision, "policy_version": CURRENT_POLICY_VERSION},
        ))
    db.commit()
    db.refresh(rec)

    return EvaluationResult(
        recommendation_id=rec.id,
        decision=decision,
        state=state,
        explanation=explanation,
        checks=checks,
    )


class RecommendationNotCandidateError(Exception):
    """Raised when asked to evaluate a row that isn't in CANDIDATE state.

    The service function `evaluate_candidate` itself is state-agnostic
    (so bulk re-evaluation tooling could reuse it later), but the public
    single-item API path requires CANDIDATE — re-deciding an
    already-decided recommendation on request isn't something this
    brick's API exposes; that's an explicit future capability (e.g. a
    re-review workflow), not an accidental side door.
    """


def evaluate_single_candidate(db: Session, user_id: uuid.UUID, recommendation_id: uuid.UUID) -> EvaluationResult:
    rec = get_recommendation(db, user_id, recommendation_id)
    if rec.state != RecommendationState.CANDIDATE:
        raise RecommendationNotCandidateError(
            f"Recommendation {recommendation_id} is in state={rec.state.value}, not candidate."
        )
    return evaluate_candidate(db, rec)


def evaluate_pending_candidates(db: Session, user_id: uuid.UUID) -> list[EvaluationResult]:
    """Evaluates every CANDIDATE-state recommendation for this user."""
    pending = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id, Recommendation.state == RecommendationState.CANDIDATE)
        .order_by(Recommendation.created_at.asc())
        .all()
    )
    return [evaluate_candidate(db, rec) for rec in pending]


def get_recommendation(db: Session, user_id: uuid.UUID, recommendation_id: uuid.UUID) -> Recommendation:
    row = (
        db.query(Recommendation)
        .filter(Recommendation.id == recommendation_id, Recommendation.user_id == user_id)
        .first()
    )
    if row is None:
        raise RecommendationNotFoundError(f"Recommendation {recommendation_id} not found")
    return row
