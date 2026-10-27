"""
Recommendation endpoints — Brick 12 (generate/list/get) + Brick 13
(evaluate).

Scope boundary, stated explicitly because it matters architecturally:
POST /generate (Brick 12) only ever produces state="candidate" rows.
POST /{id}/evaluate and POST /evaluate-pending (Brick 13) are the only
things in this codebase that may move a row past CANDIDATE, and they do
so via deterministic safety/suitability checks only — never an
unconditional "approve" action, and never client-settable: there is no
request body on either evaluate endpoint, nothing the caller sends can
influence the decision. Even after evaluation, nothing in this file
exposes a "present this to the user" action — that remains a later
brick. Returning a user's own rows to that same authenticated user is a
standard scoped read (same posture as every other GET in this API),
not "publishing a recommendation."

POST /{id}/evaluate requires the row to currently be in CANDIDATE state
(409 if not) — re-deciding an already-decided recommendation isn't a
capability this API exposes (see
safety_suitability_service.RecommendationNotCandidateError).

There is no PATCH/PUT here — recommendations are never client-edited.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.recommendation import RecommendationState
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.explanation import ExplanationRead
from app.schemas.recommendation import EvaluationResultRead, GenerationResultRead, RecommendationRead
from app.services import explanation_service
from app.services import recommendation_service as service
from app.services import safety_suitability_service as safety_service
from app.services import metrics_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/generate", response_model=GenerationResultRead, status_code=status.HTTP_201_CREATED)
def generate_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationResultRead:
    result = service.generate_candidates(db, current_user.id)
    return GenerationResultRead.model_validate(
        {
            "context_status": result.context_status,
            "candidates": result.candidates,
            "skipped": result.skipped,
        }
    )


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    state: RecommendationState | None = None,
) -> list[RecommendationRead]:
    rows = service.list_recommendations(db, current_user.id, state=state)
    latest = metrics_service.get_latest_computation(db, current_user.id)
    latest_id = str(latest[0]) if latest else None
    result = []
    for row in rows:
        payload = RecommendationRead.model_validate(row).model_dump()
        source_id = (row.based_on or {}).get("computation_id")
        payload["current_for_profile"] = latest_id is not None and str(source_id) == latest_id
        result.append(RecommendationRead.model_validate(payload))
    return result


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecommendationRead:
    try:
        row = service.get_recommendation(db, current_user.id, recommendation_id)
    except service.RecommendationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecommendationRead.model_validate(row)


@router.post("/evaluate-pending", response_model=list[EvaluationResultRead])
def evaluate_pending_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EvaluationResultRead]:
    """Runs the Brick 13 safety/suitability gate over every CANDIDATE-state
    recommendation this user currently has. No request body — the gate's
    decision is entirely a function of the candidate's own stored data
    and the user's current metrics, never client input."""
    results = safety_service.evaluate_pending_candidates(db, current_user.id)
    return [EvaluationResultRead.model_validate(r) for r in results]


@router.post("/{recommendation_id}/evaluate", response_model=EvaluationResultRead)
def evaluate_recommendation(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationResultRead:
    try:
        result = safety_service.evaluate_single_candidate(db, current_user.id, recommendation_id)
    except safety_service.RecommendationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except safety_service.RecommendationNotCandidateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return EvaluationResultRead.model_validate(result)


@router.get("/{recommendation_id}/explanation", response_model=ExplanationRead)
def get_recommendation_explanation(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExplanationRead:
    """Brick 14 — works for a recommendation in ANY state (CANDIDATE
    through EVALUATED); the explanation itself notes when safety review
    hasn't happened yet rather than refusing to explain an unreviewed
    candidate."""
    try:
        explanation = explanation_service.build_explanation(db, current_user.id, recommendation_id)
    except explanation_service.RecommendationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ExplanationRead.model_validate(explanation)
