"""
Application configuration.

All configuration is loaded from environment variables / a local .env
file. No secrets are hard-coded here — see .env.example at the repo root
for the documented set of variables.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = "FinGuide+"
    app_version: str = "0.1.0"
    app_description: str = (
        "FinGuide+ API — validated, evidence-aware, safety-gated personal "
        "finance decision support with traceable recommendation lifecycle controls."
    )
    environment: str = "development"
    debug: bool = True
    secret_key: str | None = None
    access_token_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    rate_limit_requests: int = Field(default=120, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # API
    api_v1_prefix: str = "/api/v1"

    # CORS (comma-separated origins in the environment variable)
    cors_allowed_origins: str = "http://localhost:5173"

    # Database
    # No credential is embedded in source. Configure DATABASE_URL locally.
    database_url: str = "postgresql+psycopg://finguide@localhost:5432/finguide"

    # Development-only fallback identity (see app/core/user_context.py).
    # It is never accepted outside development.
    dev_user_email: str = "dev@finguide.local"

    # Chat provider. Users must consent before conversation content is sent
    # to any external LLM provider.
    chatbot_provider: str = "rule_based"
    openai_api_key: str | None = None
    openai_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_fallback_model: str | None = "gemini-3.5-flash-lite"
    openai_timeout_seconds: float = Field(default=30, ge=5, le=120)
    openai_max_output_tokens: int = Field(default=700, ge=64, le=4000)
    chatbot_max_context_chars: int = Field(default=18000, ge=4000, le=100000)

    @model_validator(mode="after")
    def validate_chat_settings(self):
        if self.chatbot_provider.lower() not in {"rule_based", "openai", "gemini"}:
            raise ValueError("CHATBOT_PROVIDER must be 'rule_based', 'openai', or 'gemini'.")
        return self

    # Brick 08 — Data Validation & Confidence. Below this confidence, an
    # otherwise-plausible extracted value is marked LOW_CONFIDENCE rather
    # than VALID. Configurable per the brick's Definition of Done.
    low_confidence_threshold: float = 0.70

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.environment.lower() != "development":
            if self.debug:
                raise ValueError("DEBUG must be false outside development.")
            if not self.secret_key or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must contain at least 32 characters outside development.")
            if "localhost" in self.cors_allowed_origins or "127.0.0.1" in self.cors_allowed_origins:
                raise ValueError("Non-development CORS origins must be explicitly configured.")
            if "*" in self.cors_allowed_origins:
                raise ValueError("Wildcard CORS origins are not allowed outside development.")
            from sqlalchemy.engine import make_url
            if not make_url(self.database_url).password:
                raise ValueError("DATABASE_URL must include a configured database credential outside development.")
        return self

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def cors_allowed_origin_regex(self) -> str | None:
        """
        In development, also allow any localhost/127.0.0.1 port.

        Vite silently picks a different port (5174, 5175, ...) when the
        configured one is already in use, which otherwise causes a
        confusing CORS failure that looks like the backend is down. The
        explicit `cors_allowed_origins_list` above remains the source of
        truth for non-development environments.
        """
        if self.environment != "development":
            return None
        return r"^http://(localhost|127\.0\.0\.1):\d+$"


settings = Settings()
