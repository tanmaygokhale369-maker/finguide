from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.user_context import bearer, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.feedback import ConsentRecord, EvaluationRecord, RecommendationAuditEvent, RecommendationFeedback, SafetyIncident
from app.models.derived_metric import DerivedMetric
from app.models.evidence import ExternalEvidence
from app.models.extracted_field import ExtractedField
from app.models.financial_profile import FinancialProfile
from app.models.recommendation import Recommendation
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.privacy import ConsentUpdate, DeleteAccountRequest
from app.services.auth_service import verify_password

router = APIRouter(prefix="/privacy", tags=["privacy and governance"])


@router.get("/consent")
def get_consent_records(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == current_user.id)
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .all()
    )
    latest_by_purpose = {}
    for row in rows:
        latest_by_purpose.setdefault(row.purpose, row)
    return [
        {
            "purpose": row.purpose,
            "granted": row.granted,
            "policy_version": row.policy_version,
            "recorded_at": row.created_at,
        }
        for row in latest_by_purpose.values()
    ]


@router.post("/consent", status_code=status.HTTP_201_CREATED)
def record_consent(payload: ConsentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = ConsentRecord(user_id=current_user.id, purpose=payload.purpose, granted=payload.granted, policy_version=payload.policy_version)
    db.add(row)
    db.commit()
    return {"purpose": row.purpose, "granted": row.granted, "policy_version": row.policy_version, "recorded_at": row.created_at}


@router.get("/export")
def export_user_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = db.query(FinancialProfile).filter(FinancialProfile.user_id == current_user.id).first()
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    recommendations = db.query(Recommendation).filter(Recommendation.user_id == current_user.id).all()
    conversations = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
    feedback = db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == current_user.id).all()
    consent = db.query(ConsentRecord).filter(ConsentRecord.user_id == current_user.id).all()
    metrics = db.query(DerivedMetric).filter(DerivedMetric.user_id == current_user.id).all()
    extracted_fields = db.query(ExtractedField).filter(ExtractedField.user_id == current_user.id).all()
    evidence = db.query(ExternalEvidence).filter(ExternalEvidence.user_id == current_user.id).all()
    incidents = db.query(SafetyIncident).filter(SafetyIncident.user_id == current_user.id).all()
    evaluation_records = db.query(EvaluationRecord).filter(EvaluationRecord.user_id == current_user.id).all()
    audit_events = db.query(RecommendationAuditEvent).filter(RecommendationAuditEvent.user_id == current_user.id).all()
    return jsonable_encoder({
        "account": {"email": current_user.email, "full_name": current_user.full_name, "created_at": current_user.created_at},
        "financial_profile": profile,
        "transactions": transactions,
        "derived_metrics": metrics,
        "extracted_fields": extracted_fields,
        "recommendations": recommendations,
        "external_evidence": evidence,
        "safety_incidents": incidents,
        "evaluation_records": evaluation_records,
        "recommendation_audit_events": audit_events,
        "conversations": [{"id": c.id, "created_at": c.created_at, "messages": [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in c.messages]} for c in conversations],
        "feedback": feedback,
        "consent_history": consent,
    })


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if not payload.confirm or not (credentials or request.cookies.get("finguide_session")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Account deletion requires an authenticated session and explicit confirmation.")
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password verification failed.")
    db.delete(current_user)
    db.commit()
    response.delete_cookie("finguide_session", path=settings.api_v1_prefix, httponly=True, secure=settings.environment.lower() in {"production", "prod"}, samesite="strict")
