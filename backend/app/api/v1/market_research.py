"""Profile-gated market research endpoint; never used as an approved advice flow."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.market_research import MutualFundGoalPlanRequest
from app.services import financial_profile_service
from app.services.market_research_service import MarketDataUnavailable, build_fund_analysis, build_mutual_fund_goal_plan, build_research_shortlist

router = APIRouter(prefix="/market-research", tags=["market-research"])


@router.get("/funds/{scheme_code}/analysis", response_model=dict)
def get_fund_analysis(scheme_code: int, current_user: User = Depends(get_current_user)) -> dict:
    """On-demand fund cost data and only verified index comparisons."""
    del current_user
    try:
        return build_fund_analysis(scheme_code)
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/plan", response_model=dict)
def create_mutual_fund_goal_plan(
    payload: MutualFundGoalPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Calculate a goal savings baseline and screen funds against its horizon."""
    try:
        profile = financial_profile_service.get_profile(db, current_user.id)
    except financial_profile_service.ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Add a financial profile before building a mutual-fund goal plan.",
        ) from exc
    return build_mutual_fund_goal_plan(profile, payload.model_dump())


@router.get("/shortlist", response_model=dict)
def get_market_research_shortlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return source-attributed research candidates from current profile data.

    The endpoint does not send user profile data to market-data providers.
    Products are research candidates only and are not persisted as approved
    recommendations in the Brick 12/13 lifecycle.
    """
    try:
        profile = financial_profile_service.get_profile(db, current_user.id)
    except financial_profile_service.ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Add a financial profile before requesting market research.",
        ) from exc

    try:
        return build_research_shortlist(profile)
    except MarketDataUnavailable as exc:
        return {
            "status": "market_data_unavailable",
            "candidates": [],
            "research_notice": "No product was selected because current source data could not be verified.",
            "unavailable_assets": [
                {"asset_class": "mutual_funds", "status": "unavailable", "reason": str(exc)},
                {"asset_class": "bonds", "status": "unavailable", "reason": "No verified free bond-quote feed is configured."},
                {"asset_class": "gold", "status": "unavailable", "reason": "The official benchmark feed requires a provider credential or licence."},
            ],
        }
