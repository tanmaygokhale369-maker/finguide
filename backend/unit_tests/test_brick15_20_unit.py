from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.news import FinBERTAnalyzer
from app.schemas.evidence import EvidenceCreate
from app.core.config import Settings
from app.services import auth_service
from app.services.auth_service import create_access_token, decode_access_token, hash_password, verify_password
from app.services.evidence_service import content_digest, read_status
from types import SimpleNamespace


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("incorrect", first)


def test_signed_session_token_round_trip_and_tamper_rejection():
    subject = uuid4()
    token = create_access_token(subject)
    assert decode_access_token(token) == subject
    with pytest.raises(Exception):
        decode_access_token(token[:-1] + ("a" if token[-1] != "a" else "b"))


def test_signed_session_token_expiry_is_enforced(monkeypatch):
    monkeypatch.setattr(auth_service.time, "time", lambda: 1_000)
    token = create_access_token(uuid4())
    monkeypatch.setattr(auth_service.time, "time", lambda: 1_000 + 31 * 60)
    with pytest.raises(Exception):
        decode_access_token(token)


def test_production_settings_fail_closed_without_secret_or_with_wildcard_cors():
    values = {"environment": "production", "debug": False, "cors_allowed_origins": "https://app.example.com", "database_url": "postgresql+psycopg://user:strong@db:5432/finguide"}
    with pytest.raises(ValidationError):
        Settings(**values)
    with pytest.raises(ValidationError):
        Settings(**{**values, "secret_key": "s" * 40, "cors_allowed_origins": "*"})
    validated = Settings(**{**values, "secret_key": "s" * 40})
    assert validated.environment == "production"


def test_news_without_local_finbert_stays_uncertain():
    result = FinBERTAnalyzer(model_path=None).analyze("Markets rose today.")
    assert result.label == "uncertain"
    assert result.confidence is None
    assert result.model_version is None


def test_evidence_digest_deduplicates_canonical_text():
    assert content_digest("  Headline ", " Text ") == content_digest("Headline", "Text")


def test_evidence_freshness_is_explicit_when_unknown_or_expired():
    now = datetime.now(timezone.utc)
    assert read_status(SimpleNamespace(valid_until=None), now)["freshness_status"] == "unknown"
    assert read_status(SimpleNamespace(valid_until=now - timedelta(seconds=1)), now)["freshness_status"] == "stale"
    assert read_status(SimpleNamespace(valid_until=now + timedelta(days=1)), now)["freshness_status"] == "fresh"


def test_evidence_requires_https_and_timezone_aware_provenance():
    timestamp = datetime.now(timezone.utc)
    valid = {
        "source_name": "Example", "source_type": "news", "source_url": "https://example.com/article",
        "retrieved_at": timestamp, "title": "Headline", "content": "Untrusted article text.",
    }
    assert EvidenceCreate(**valid).source_type == "news"
    with pytest.raises(ValidationError):
        EvidenceCreate(**{**valid, "source_url": "http://example.com/article"})
    with pytest.raises(ValidationError):
        EvidenceCreate(**{**valid, "retrieved_at": timestamp.replace(tzinfo=None)})
