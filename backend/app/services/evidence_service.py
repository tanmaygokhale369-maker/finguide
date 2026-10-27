"""External evidence boundary. No provider is configured, so ingestion is explicit.

Client supplied records are retained as unverified and cannot be treated as
trusted recommendation evidence. Production providers must implement this
interface and establish source identity before setting verification_status.
"""
import hashlib
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.news import get_sentiment_analyzer
from app.models.evidence import ExternalEvidence


class EvidenceProviderUnavailable(Exception):
    pass


class ExternalEvidenceProvider(Protocol):
    """Adapter contract for real providers; implementations must return raw provenance."""
    provider_id: str

    def retrieve(self, query: str) -> list[dict]: ...


def get_external_provider() -> ExternalEvidenceProvider:
    """Fail closed until a verified provider is configured and credentialed."""
    raise EvidenceProviderUnavailable("No external financial-data provider is configured.")


def content_digest(title: str, content: str) -> str:
    return hashlib.sha256((title.strip() + "\n" + content.strip()).encode("utf-8")).hexdigest()


def create_user_submitted_evidence(db: Session, user_id, payload) -> ExternalEvidence:
    digest = content_digest(payload.title, payload.content)
    existing = db.query(ExternalEvidence).filter(
        ExternalEvidence.user_id == user_id,
        ExternalEvidence.content_hash == digest,
    ).first()
    if existing:
        if existing.source_name != payload.source_name:
            metadata = dict(existing.conflict_metadata or {})
            duplicates = list(metadata.get("duplicate_sources", []))
            source = {"source_name": payload.source_name, "source_url": str(payload.source_url), "retrieved_at": payload.retrieved_at.isoformat()}
            if source not in duplicates:
                duplicates.append(source)
                metadata["duplicate_sources"] = duplicates
                existing.conflict_metadata = metadata
                db.commit()
        return existing
    same_title = db.query(ExternalEvidence).filter(
        ExternalEvidence.user_id == user_id,
        ExternalEvidence.source_type == payload.source_type,
        func.lower(ExternalEvidence.title) == payload.title.strip().lower(),
    ).all()
    sentiment = get_sentiment_analyzer().analyze(payload.content) if payload.source_type == "news" else None
    row = ExternalEvidence(
        user_id=user_id,
        source_name=payload.source_name,
        source_type=payload.source_type,
        source_url=str(payload.source_url),
        retrieved_at=payload.retrieved_at,
        published_at=payload.published_at,
        valid_until=payload.valid_until,
        credibility=0,
        content_hash=digest,
        title=payload.title,
        content=payload.content,
        relevance=payload.relevance,
        conflict_metadata={
            "verification": "Client supplied; publisher identity not verified.",
            "conflicting_evidence_ids": [str(item.id) for item in same_title if item.content_hash != digest],
        },
        sentiment_label=sentiment.label if sentiment else "uncertain",
        sentiment_confidence=sentiment.confidence if sentiment else None,
        sentiment_model=sentiment.model_version if sentiment else None,
        verification_status="unverified",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if same_title:
        for prior in same_title:
            metadata = dict(prior.conflict_metadata or {})
            ids = list(metadata.get("conflicting_evidence_ids", []))
            if str(row.id) not in ids:
                ids.append(str(row.id))
                metadata["conflicting_evidence_ids"] = ids
                prior.conflict_metadata = metadata
        db.commit()
    return row


def read_status(row: ExternalEvidence, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    expires = row.valid_until
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    freshness = "stale" if expires is not None and expires <= now else ("unknown" if expires is None else "fresh")
    return {"freshness_status": freshness}
