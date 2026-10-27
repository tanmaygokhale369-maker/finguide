import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.user_context import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.holding import HoldingCreate, HoldingRead, HoldingUpdate
from app.schemas.holding_activity import HoldingActivityCreate, HoldingActivityRead
from app.services import holding_service, market_research_service

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("/schemes")
def search_schemes(q: str = Query(min_length=2, max_length=100), current_user: User = Depends(get_current_user)) -> list[dict]:
    del current_user
    try:
        payload = market_research_service._json_from_provider("/mf/search", query={"q": q})
    except market_research_service.MarketDataUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not isinstance(payload, list):
        return []
    return [{"scheme_code": x["schemeCode"], "scheme_name": x["schemeName"]} for x in payload[:30] if isinstance(x, dict) and isinstance(x.get("schemeCode"), int) and x.get("schemeName")]


@router.get("", response_model=list[HoldingRead])
def list_holdings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    return holding_service.list_holdings(db, current_user.id)


@router.post("", response_model=HoldingRead, status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> HoldingRead:
    try:
        item = holding_service.create_holding(db, current_user.id, payload)
    except market_research_service.MarketDataUnavailable as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    data = holding_service.list_holdings(db, current_user.id)
    return HoldingRead.model_validate(next(x for x in data if x["id"] == item.id))


@router.patch("/{holding_id}", response_model=HoldingRead)
def update_holding(holding_id: uuid.UUID, payload: HoldingUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> HoldingRead:
    try:
        holding_service.update_holding(db, current_user.id, holding_id, payload)
    except holding_service.HoldingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found") from exc
    return HoldingRead.model_validate(next(x for x in holding_service.list_holdings(db, current_user.id) if x["id"] == holding_id))


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    try:
        holding_service.delete_holding(db, current_user.id, holding_id)
    except holding_service.HoldingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found") from exc


@router.get("/{holding_id}/activity", response_model=list[HoldingActivityRead])
def list_holding_activity(holding_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list:
    try:
        return holding_service.list_activities(db, current_user.id, holding_id)
    except holding_service.HoldingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found") from exc


@router.post("/{holding_id}/activity", response_model=HoldingActivityRead, status_code=status.HTTP_201_CREATED)
def create_holding_activity(holding_id: uuid.UUID, payload: HoldingActivityCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> HoldingActivityRead:
    try:
        return holding_service.create_activity(db, current_user.id, holding_id, payload)
    except holding_service.HoldingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found") from exc
    except holding_service.InsufficientHoldingUnitsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Redemption units exceed the saved holding balance.") from exc


@router.delete("/{holding_id}/activity/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding_activity(holding_id: uuid.UUID, activity_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    try:
        holding_service.delete_activity(db, current_user.id, holding_id, activity_id)
    except holding_service.HoldingNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found") from exc
    except holding_service.HoldingActivityNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
