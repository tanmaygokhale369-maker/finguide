"""
Spending Analysis endpoint — Brick 11.

Read-only. start_date/end_date are required query parameters, not
defaulted — "Date ranges explicit" per the plan's Definition of Done,
and consistent with the "no silent assumptions" rule: picking an
implicit range (e.g. "this month") on the caller's behalf would be a
silent assumption about what they meant.
"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.spending_analysis import SpendingAnalysisRead
from app.services import spending_analysis_service as service

router = APIRouter(prefix="/spending", tags=["spending"])


@router.get("/analysis", response_model=SpendingAnalysisRead)
def get_spending_analysis(
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpendingAnalysisRead:
    try:
        analysis = service.analyze_spending(db, current_user.id, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SpendingAnalysisRead.model_validate(analysis)
