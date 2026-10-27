from pydantic import EmailStr, Field

from app.schemas.common import ApiBaseModel


class RegisterRequest(ApiBaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    financial_analysis_consent: bool


class LoginRequest(ApiBaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthSessionResponse(ApiBaseModel):
    authenticated: bool = True
    expires_in: int
