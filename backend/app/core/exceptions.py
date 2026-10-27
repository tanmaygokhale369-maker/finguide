"""
Global exception handlers.

Brick 03 scope: translate every failure — validation errors, HTTP
exceptions (including "not found" for unmatched routes), and unhandled
exceptions — into the single ErrorResponse envelope defined in
app/schemas/common.py, and log unhandled exceptions server-side.

This is generic API-foundation behavior. Domain-specific safety/policy
error types (e.g. CLARIFY/BLOCK/ESCALATE recommendation outcomes) belong
to the bricks that own those decisions (08, 13) and are not modeled here.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def _error_response(status_code: int, error_type: str, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(type=error_type, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(field=".".join(str(part) for part in error["loc"]), message=error["msg"])
        for error in exc.errors()
    ]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "The request could not be validated.",
        details,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, "http_error", str(exc.detail))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Do not log exception text or SQL parameters: those can contain user
    # supplied financial values. Keep only non-sensitive routing context.
    logger.error("Unhandled %s while processing %s %s", type(exc).__name__, request.method, request.url.path)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "An unexpected error occurred.",
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
