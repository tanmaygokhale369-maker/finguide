from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.evidence import ExternalEvidence
from app.models.feedback import ConsentRecord
from app.models.user import User
from app.schemas.evidence import EvidenceCreate, EvidenceRead
from app.services.evidence_service import create_user_submitted_evidence, read_status

router = APIRouter(prefix="/evidence", tags=["external evidence"])


def _read(row: ExternalEvidence) -> EvidenceRead:
    return EvidenceRead.model_validate({
        "id": str(row.id), "source_name": row.source_name, "source_type": row.source_type,
        "source_url": row.source_url, "retrieved_at": row.retrieved_at,
        "published_at": row.published_at, "valid_until": row.valid_until,
        "credibility": row.credibility, "content_hash": row.content_hash,
        "title": row.title, "relevance": row.relevance,
        "verification_status": row.verification_status,
        "conflict_metadata": row.conflict_metadata,
        "freshness_status": read_status(row)["freshness_status"],
        "sentiment_label": row.sentiment_label,
        "sentiment_confidence": row.sentiment_confidence,
        "sentiment_model": row.sentiment_model,
    })


@router.post("", response_model=EvidenceRead)
def submit_evidence(payload: EvidenceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EvidenceRead:
    if payload.source_type == "news" and settings.environment.lower() in {"production", "prod"}:
        news_consent = db.query(ConsentRecord).filter(
            ConsentRecord.user_id == current_user.id,
            ConsentRecord.purpose == "external_news_analysis",
        ).order_by(desc(ConsentRecord.created_at)).first()
        if news_consent is None or not news_consent.granted:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "External news analysis consent is required.")
    row = create_user_submitted_evidence(db, current_user.id, payload)
    return _read(row)


@router.get("", response_model=list[EvidenceRead])
def list_evidence(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[EvidenceRead]:
    rows = db.query(ExternalEvidence).filter(ExternalEvidence.user_id == current_user.id).order_by(ExternalEvidence.retrieved_at.desc()).all()
    return [_read(row) for row in rows]
