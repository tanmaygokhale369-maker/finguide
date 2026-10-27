"""
User-context abstraction.

Every endpoint that needs the current user depends on `get_current_user`;
client-supplied user IDs never establish identity. Production resolves
the user from a signed bearer token or HttpOnly session cookie and checks
the current financial-analysis consent. A fixed development user is
available only when `ENVIRONMENT=development`.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.feedback import ConsentRecord
from app.services.auth_service import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    token = credentials.credentials if credentials is not None else request.cookies.get("finguide_session")
    if token is not None:
        user_id = decode_access_token(token)
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or inactive account.", headers={"WWW-Authenticate": "Bearer"})
        if settings.environment.lower() in {"production", "prod"} and not request.url.path.startswith(("/api/v1/privacy", "/api/v1/auth")):
            consent = db.query(ConsentRecord).filter(ConsentRecord.user_id == user.id, ConsentRecord.purpose == "financial_analysis").order_by(desc(ConsentRecord.created_at)).first()
            if consent is None or not consent.granted:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Financial analysis consent is required to use this endpoint.")
        return user

    if settings.environment != "development":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == settings.dev_user_email).first()
    if user is None:
        user = User(email=settings.dev_user_email, full_name="Development User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
