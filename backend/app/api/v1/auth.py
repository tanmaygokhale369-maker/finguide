from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.feedback import ConsentRecord
from app.schemas.auth import AuthSessionResponse, LoginRequest, RegisterRequest
from app.services.auth_service import create_access_token, hash_password, verify_password
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_session(response: Response, user: User) -> AuthSessionResponse:
    ttl = settings.access_token_ttl_minutes * 60
    response.set_cookie("finguide_session", create_access_token(user.id), max_age=ttl, httponly=True, secure=settings.environment.lower() in {"production", "prod"}, samesite="strict", path=settings.api_v1_prefix)
    return AuthSessionResponse(expires_in=ttl)


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthSessionResponse:
    if not payload.financial_analysis_consent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Financial analysis consent is required to create an account.")
    email = payload.email.strip().lower()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(ConsentRecord(user_id=user.id, purpose="financial_analysis", granted=True, policy_version="v1"))
    db.commit()
    return _set_session(response, user)


@router.post("/login", response_model=AuthSessionResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthSessionResponse:
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.", headers={"WWW-Authenticate": "Bearer"})
    return _set_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie("finguide_session", path=settings.api_v1_prefix, httponly=True, secure=settings.environment.lower() in {"production", "prod"}, samesite="strict")
