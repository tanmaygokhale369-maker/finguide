"""
Health check endpoint.

A simple liveness check confirming the API process is up and
configuration loaded successfully, plus a readiness check that verifies
the database is actually reachable (added in Brick 04, as flagged by
this file's earlier comment). Liveness intentionally stays independent
of the database — a slow/unreachable DB should surface as a readiness
failure, not make the process look dead entirely.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadinessResponse
from app.core.middleware import _metrics, _requests_lock

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )


@router.get("/readiness", response_model=ReadinessResponse)
def get_readiness(db: Session = Depends(get_db)) -> ReadinessResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unreachable") from exc
    return ReadinessResponse(status="ok", database="ok")


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def get_metrics() -> str:
    """Low-cardinality process metrics; scrape through a trusted network."""
    with _requests_lock:
        values = dict(_metrics)
    return (
        "# TYPE finguide_http_requests_total counter\n"
        f"finguide_http_requests_total {values.get('requests_total', 0)}\n"
        "# TYPE finguide_http_server_errors_total counter\n"
        f"finguide_http_server_errors_total {values.get('server_errors_total', 0)}\n"
        "# TYPE finguide_http_request_duration_seconds_total counter\n"
        f"finguide_http_request_duration_seconds_total {values.get('request_duration_seconds_total', 0):.6f}\n"
    )
