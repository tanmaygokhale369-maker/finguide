import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.feedback import EvaluationRecord, RecommendationAuditEvent, RecommendationFeedback, SafetyIncident
from app.models.recommendation import Recommendation, RecommendationState
from app.models.user import User
from app.schemas.feedback import EvaluationMetricRead, EvaluationSummaryRead, FeedbackCreate, FeedbackRead

router = APIRouter(tags=["feedback and evaluation"])


@router.post("/recommendations/{recommendation_id}/present", response_model=dict)
def present_recommendation(recommendation_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(Recommendation).filter(Recommendation.id == recommendation_id, Recommendation.user_id == current_user.id).with_for_update().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
    if row.state not in {RecommendationState.APPROVED, RecommendationState.MODIFIED}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only safety-approved recommendations can be presented.")
    old_state = row.state.value
    row.state = RecommendationState.PRESENTED
    db.add(RecommendationAuditEvent(user_id=current_user.id, recommendation_id=row.id, from_state=old_state, to_state="presented", event_type="presented", metadata_json={"policy_version": row.policy_version}))
    db.commit()
    return {"recommendation_id": str(row.id), "state": "presented"}


@router.post("/recommendations/{recommendation_id}/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_feedback(recommendation_id: uuid.UUID, payload: FeedbackCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FeedbackRead:
    row = db.query(Recommendation).filter(Recommendation.id == recommendation_id, Recommendation.user_id == current_user.id).with_for_update().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
    if row.state != RecommendationState.PRESENTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Feedback is accepted only for a presented recommendation.")
    feedback = RecommendationFeedback(user_id=current_user.id, recommendation_id=row.id, action=payload.action, rating=payload.rating, comment=payload.comment)
    db.add(feedback)
    db.flush()
    incident = payload.rating == "harmful"
    if incident:
        db.add(SafetyIncident(user_id=current_user.id, recommendation_id=row.id, feedback_id=feedback.id, status="open"))
    previous = row.state.value
    action_state = {"accepted": RecommendationState.ACCEPTED, "rejected": RecommendationState.REJECTED, "ignored": RecommendationState.IGNORED}[payload.action]
    row.state = action_state
    db.add(RecommendationAuditEvent(user_id=current_user.id, recommendation_id=row.id, from_state=previous, to_state=action_state.value, event_type="user_feedback", metadata_json={"rating": payload.rating, "incident_created": incident}))
    row.state = RecommendationState.EVALUATED
    db.add(RecommendationAuditEvent(user_id=current_user.id, recommendation_id=row.id, from_state=action_state.value, to_state=RecommendationState.EVALUATED.value, event_type="feedback_evaluated", metadata_json={"feedback_id": str(feedback.id)}))
    db.commit()
    db.refresh(feedback)
    return FeedbackRead(id=str(feedback.id), recommendation_id=str(row.id), action=feedback.action, rating=feedback.rating, incident_created=incident)


@router.get("/evaluation/summary", response_model=EvaluationSummaryRead)
def evaluation_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EvaluationSummaryRead:
    rows = db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == current_user.id).all()
    total = len(rows)
    accepted = sum(r.action == "accepted" for r in rows)
    rated = [r for r in rows if r.rating in {"helpful", "not_helpful"}]
    helpful = sum(r.rating == "helpful" for r in rated)
    harmful = sum(r.rating == "harmful" for r in rows)
    reviewed = db.query(Recommendation).filter(Recommendation.user_id == current_user.id, Recommendation.suitability_status.is_not(None)).all()
    blocked = sum(r.state in {RecommendationState.BLOCKED, RecommendationState.CLARIFY, RecommendationState.ESCALATE} for r in reviewed)
    metrics = [
        EvaluationMetricRead(metric_name="accepted_feedback_rate", numerator=accepted, denominator=total, result=accepted / total if total else None),
        EvaluationMetricRead(metric_name="helpful_rate_among_non_harmful_ratings", numerator=helpful, denominator=len(rated), result=helpful / len(rated) if rated else None),
        EvaluationMetricRead(metric_name="harmful_feedback_rate", numerator=harmful, denominator=total, result=harmful / total if total else None),
        EvaluationMetricRead(metric_name="safety_block_clarify_escalate_rate", numerator=blocked, denominator=len(reviewed), result=blocked / len(reviewed) if reviewed else None),
    ]
    incidents = db.query(func.count(SafetyIncident.id)).filter(SafetyIncident.user_id == current_user.id, SafetyIncident.status == "open").scalar() or 0
    return EvaluationSummaryRead(scope="current_user_feedback; descriptive signal, not proof of financial correctness", metrics=metrics, incidents_open=incidents)


@router.post("/evaluation/run", response_model=list[EvaluationMetricRead], status_code=status.HTTP_201_CREATED)
def record_evaluation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[EvaluationMetricRead]:
    summary = evaluation_summary(db, current_user)
    saved = []
    for metric in summary.metrics:
        entry = EvaluationRecord(user_id=current_user.id, evaluation_type="user_feedback_snapshot", metric_name=metric.metric_name, numerator=metric.numerator, denominator=metric.denominator, result=metric.result, details={"limitations": summary.scope})
        db.add(entry)
        saved.append(entry)
    db.commit()
    return summary.metrics
