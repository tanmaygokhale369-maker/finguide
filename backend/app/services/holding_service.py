import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.holding import MutualFundHolding
from app.models.holding_activity import HoldingActivity
from app.schemas.holding import HoldingCreate, HoldingUpdate
from app.schemas.holding_activity import HoldingActivityCreate
from app.services import market_research_service


class HoldingNotFoundError(Exception):
    pass


class HoldingActivityNotFoundError(Exception):
    pass


class InsufficientHoldingUnitsError(Exception):
    pass


def list_holdings(db: Session, user_id: uuid.UUID) -> list[dict]:
    holdings = db.query(MutualFundHolding).filter(MutualFundHolding.user_id == user_id).order_by(MutualFundHolding.created_at.desc()).all()
    output = []
    for holding in holdings:
        item = {key: getattr(holding, key) for key in ("id", "scheme_code", "scheme_name", "units", "amount_invested", "monthly_sip", "redemption_proceeds", "created_at", "updated_at")}
        item["activity_count"] = db.query(HoldingActivity).filter(HoldingActivity.holding_id == holding.id, HoldingActivity.user_id == user_id).count()
        item["scheme_category"] = None
        try:
            quote = market_research_service.get_latest_scheme_nav(holding.scheme_code)
            nav = Decimal(quote["nav"])
            item.update(scheme_category=quote["scheme_category"], current_nav=nav, current_value=(holding.units * nav).quantize(Decimal("0.01")), nav_date=quote["date"], valuation_status="available")
        except (market_research_service.MarketDataUnavailable, InvalidOperation, KeyError, TypeError):
            item.update(current_nav=None, current_value=None, nav_date=None, valuation_status="unavailable")
        output.append(item)
    return output


def create_holding(db: Session, user_id: uuid.UUID, data: HoldingCreate) -> MutualFundHolding:
    meta, history = market_research_service._nav_history(data.scheme_code)
    name = str(meta.get("scheme_name") or "").strip()
    if not name:
        raise market_research_service.MarketDataUnavailable("The provider did not return a verified scheme name.")
    item = MutualFundHolding(user_id=user_id, scheme_code=data.scheme_code, scheme_name=name, units=data.units, amount_invested=data.amount_invested, monthly_sip=data.monthly_sip)
    db.add(item)
    db.flush()
    db.add(HoldingActivity(user_id=user_id, holding_id=item.id, activity_type="opening_balance", units_delta=data.units, amount=data.amount_invested, activity_date=date.today(), note="Initial saved position; exact purchase date was not provided."))
    db.commit()
    db.refresh(item)
    return item


def update_holding(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID, data: HoldingUpdate) -> MutualFundHolding:
    item = db.query(MutualFundHolding).filter(MutualFundHolding.id == holding_id, MutualFundHolding.user_id == user_id).first()
    if item is None:
        raise HoldingNotFoundError
    updates = data.model_dump(exclude_unset=True)
    old_units = item.units
    for key, value in updates.items():
        setattr(item, key, value)
    if "units" in updates and updates["units"] != old_units:
        delta = updates["units"] - old_units
        db.add(HoldingActivity(user_id=user_id, holding_id=item.id, activity_type="adjustment", units_delta=delta, amount=None, activity_date=date.today(), note="Manual unit reconciliation."))
    db.commit()
    db.refresh(item)
    return item


def delete_holding(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID) -> None:
    item = db.query(MutualFundHolding).filter(MutualFundHolding.id == holding_id, MutualFundHolding.user_id == user_id).first()
    if item is None:
        # DELETE is idempotent: a stale page or repeated request should
        # leave the portfolio in the requested state without a 404.
        return
    db.delete(item)
    db.commit()


def list_activities(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID) -> list[HoldingActivity]:
    get_holding(db, user_id, holding_id)
    return db.query(HoldingActivity).filter(HoldingActivity.user_id == user_id, HoldingActivity.holding_id == holding_id).order_by(HoldingActivity.activity_date.desc(), HoldingActivity.created_at.desc()).all()


def get_holding(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID, *, lock: bool = False) -> MutualFundHolding:
    query = db.query(MutualFundHolding).filter(MutualFundHolding.id == holding_id, MutualFundHolding.user_id == user_id)
    if lock:
        query = query.with_for_update()
    item = query.first()
    if item is None:
        raise HoldingNotFoundError
    return item


def create_activity(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID, data: HoldingActivityCreate) -> HoldingActivity:
    holding = get_holding(db, user_id, holding_id, lock=True)
    if data.activity_type == "redemption" and data.units > holding.units:
        raise InsufficientHoldingUnitsError
    delta = -data.units if data.activity_type == "redemption" else data.units
    activity = HoldingActivity(user_id=user_id, holding_id=holding_id, activity_type=data.activity_type, units_delta=delta, amount=data.amount, activity_date=data.activity_date, note=data.note)
    holding.units = holding.units + delta
    if data.activity_type == "purchase" and holding.amount_invested is not None:
        holding.amount_invested += data.amount or Decimal("0")
    elif data.activity_type == "redemption":
        holding.redemption_proceeds += data.amount or Decimal("0")
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def delete_activity(db: Session, user_id: uuid.UUID, holding_id: uuid.UUID, activity_id: uuid.UUID) -> None:
    holding = get_holding(db, user_id, holding_id, lock=True)
    activity = db.query(HoldingActivity).filter(HoldingActivity.id == activity_id, HoldingActivity.holding_id == holding_id, HoldingActivity.user_id == user_id).first()
    if activity is None:
        raise HoldingActivityNotFoundError
    if activity.activity_type == "opening_balance":
        raise ValueError("The opening-balance entry cannot be removed. Delete the holding if it was added by mistake.")
    if holding.units - activity.units_delta < 0:
        raise ValueError("This activity cannot be removed because later transactions depend on its units.")
    holding.units -= activity.units_delta
    if activity.activity_type == "purchase" and holding.amount_invested is not None:
        holding.amount_invested = max(Decimal("0"), holding.amount_invested - (activity.amount or Decimal("0")))
    elif activity.activity_type == "redemption":
        holding.redemption_proceeds = max(Decimal("0"), holding.redemption_proceeds - (activity.amount or Decimal("0")))
    db.delete(activity)
    db.commit()
