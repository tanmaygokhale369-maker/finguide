"""
Financial profile endpoints.

Every endpoint depends on `get_current_user` for identity — never on a
client-supplied user_id. See app/core/user_context.py.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.financial_metrics import ComputationSummary, DerivedMetricRead
from app.schemas.financial_profile import FinancialProfileRead, FinancialProfileUpdate
from app.services import financial_profile_service as service
from app.services import metrics_service

router = APIRouter(prefix="/profile", tags=["financial-profile"])


@router.post("", response_model=FinancialProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: FinancialProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialProfileRead:
    try:
        profile = service.create_profile(db, current_user.id, payload)
    except service.ProfileAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return FinancialProfileRead.model_validate(profile)


@router.get("", response_model=FinancialProfileRead)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialProfileRead:
    try:
        profile = service.get_profile(db, current_user.id)
    except service.ProfileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FinancialProfileRead.model_validate(profile)


@router.patch("", response_model=FinancialProfileRead)
def update_profile(
    payload: FinancialProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialProfileRead:
    try:
        profile = service.update_profile(db, current_user.id, payload)
    except service.ProfileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FinancialProfileRead.model_validate(profile)


@router.get("/metrics", response_model=list[DerivedMetricRead])
def get_current_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DerivedMetricRead]:
    """Computes every derived metric fresh from the current profile state
    and persists this as a new entry in the metrics history."""
    try:
        profile = service.get_profile(db, current_user.id)
    except service.ProfileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _computation_id, rows = metrics_service.compute_and_store_metrics(db, profile)
    return [DerivedMetricRead.model_validate(row) for row in rows]


@router.get("/metrics/history", response_model=list[ComputationSummary])
def get_metrics_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ComputationSummary]:
    """Lists every past metrics computation for this user, most recent
    first — one entry per computation, not per metric."""
    history = metrics_service.list_computation_history(db, current_user.id)
    return [ComputationSummary(computation_id=cid, calculated_at=ts) for cid, ts in history]


@router.get("/metrics/history/{computation_id}", response_model=list[DerivedMetricRead])
def get_metrics_computation(
    computation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DerivedMetricRead]:
    rows = metrics_service.get_computation_by_id(db, current_user.id, computation_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No metrics computation {computation_id} found.")
    return [DerivedMetricRead.model_validate(row) for row in rows]
