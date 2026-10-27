"""
Validation endpoints.

Read-only: nothing here writes to FinancialProfile or ExtractedField —
`revalidate_field` runs as a side effect of extraction (see
app/services/extraction_service.py), not from these routes. This is
purely a view over already-computed state, scoped to the current user
like every other endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.validation import FieldValidationSummaryRead
from app.services import validation_service

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/fields", response_model=list[FieldValidationSummaryRead])
def get_all_field_validations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FieldValidationSummaryRead]:
    summaries = validation_service.get_all_field_summaries(db, current_user.id)
    return [FieldValidationSummaryRead.model_validate(s) for s in summaries]


@router.get("/fields/{field_name}", response_model=FieldValidationSummaryRead)
def get_field_validation(
    field_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldValidationSummaryRead:
    if field_name not in validation_service.TRACKED_FIELDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"'{field_name}' is not a tracked field.")
    summary = validation_service.get_field_summary(db, current_user.id, field_name)
    return FieldValidationSummaryRead.model_validate(summary)
