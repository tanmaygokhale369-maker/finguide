"""
FinancialProfile service.

Brick 05 scope: create/get/update against the DB. Derived metrics
(savings ratio, debt-to-income, etc.) belong to Brick 09, not here — this
only persists what the user told us, unmodified.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.financial_profile import FinancialProfile
from app.schemas.financial_profile import FinancialProfileUpdate


class ProfileAlreadyExistsError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


def get_profile(db: Session, user_id: uuid.UUID) -> FinancialProfile:
    profile = db.query(FinancialProfile).filter(FinancialProfile.user_id == user_id).first()
    if profile is None:
        raise ProfileNotFoundError(f"No financial profile exists for user {user_id}")
    return profile


def create_profile(db: Session, user_id: uuid.UUID, data: FinancialProfileUpdate) -> FinancialProfile:
    existing = db.query(FinancialProfile).filter(FinancialProfile.user_id == user_id).first()
    if existing is not None:
        raise ProfileAlreadyExistsError(f"A financial profile already exists for user {user_id}")

    # Only fields explicitly provided in the request are set; anything
    # omitted stays NULL (unknown), never defaulted to 0.
    provided_fields = data.model_dump(exclude_unset=True)
    profile = FinancialProfile(user_id=user_id, **provided_fields)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user_id: uuid.UUID, data: FinancialProfileUpdate) -> FinancialProfile:
    profile = get_profile(db, user_id)  # raises ProfileNotFoundError if missing

    provided_fields = data.model_dump(exclude_unset=True)
    for field_name, value in provided_fields.items():
        setattr(profile, field_name, value)

    db.commit()
    db.refresh(profile)
    return profile
