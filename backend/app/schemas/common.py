"""
Shared response schemas.

Brick 03 scope: a single, consistent error envelope used across the API,
plus a base model other schemas can extend. Domain schemas (financial
profile, transactions, etc.) are added in the bricks that own that data.
"""

from pydantic import BaseModel, ConfigDict


class ApiBaseModel(BaseModel):
    """Base for all API schemas — forbids unexpected fields by default,
    and allows building read schemas directly from ORM objects."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorDetail(ApiBaseModel):
    """One field-level validation problem."""

    field: str
    message: str


class ErrorBody(ApiBaseModel):
    type: str
    message: str
    details: list[ErrorDetail] = []


class ErrorResponse(ApiBaseModel):
    """
    The single error shape returned by every failure in this API:

    {"error": {"type": "...", "message": "...", "details": [...]}}

    `type` is a stable machine-readable category (e.g. "validation_error",
    "http_error", "internal_error") — not the HTTP status text — so
    frontend code can branch on it without parsing messages.
    """

    error: ErrorBody
