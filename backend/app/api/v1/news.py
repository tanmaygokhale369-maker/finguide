"""Free, official-source financial headline updates."""
from fastapi import APIRouter, Depends

from app.core.user_context import get_current_user
from app.models.user import User
from app.services.news_service import get_official_financial_updates

router = APIRouter(prefix="/news", tags=["financial news"])


@router.get("/official-updates", response_model=dict)
def official_updates(current_user: User = Depends(get_current_user)) -> dict:
    """Return RBI and SEBI RSS headlines with local, optional headline tone."""
    del current_user
    return get_official_financial_updates()
