"""
Request logging middleware.

Logs method, path, status code, and duration for every request. Does not
log request/response bodies or headers, since those may contain
financial data or credentials — bulk body logging is explicitly out of
scope until a redaction policy exists (see Brick 19 security rules).
"""

import time
from collections import Counter, defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings

from app.core.logging import get_logger

logger = get_logger("app.request")
_requests: dict[str, deque[float]] = defaultdict(deque)
_requests_lock = Lock()
_metrics: Counter = Counter()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        with _requests_lock:
            _metrics["requests_total"] += 1
            _metrics["request_duration_seconds_total"] += duration_ms / 1000
            if response.status_code >= 500:
                _metrics["server_errors_total"] += 1
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Conservative per-process IP limiter plus baseline browser headers.

    Multi-instance deployments should also enforce shared limits at their
    gateway; this limiter intentionally does not trust forwarded IP headers.
    """
    async def dispatch(self, request: Request, call_next):
        exempt = request.url.path.endswith("/health") or request.url.path.endswith("/readiness")
        if not exempt and settings.environment.lower() != "development":
            # In production the only public ingress is the bundled Nginx;
            # it overwrites X-Real-IP from the actual socket peer.
            key = request.headers.get("x-real-ip") if settings.environment.lower() in {"production", "prod"} else None
            key = key or (request.client.host if request.client else "unknown")
            now = time.monotonic()
            with _requests_lock:
                if len(_requests) > 5000:
                    expired = [ip for ip, times in _requests.items() if not times or now - times[-1] >= settings.rate_limit_window_seconds]
                    for ip in expired:
                        _requests.pop(ip, None)
                bucket = _requests[key]
                while bucket and now - bucket[0] >= settings.rate_limit_window_seconds:
                    bucket.popleft()
                if len(bucket) >= settings.rate_limit_requests:
                    response = JSONResponse(status_code=429, content={"error": {"type": "rate_limit_error", "message": "Too many requests. Try again later.", "details": []}})
                    response.headers["Retry-After"] = str(settings.rate_limit_window_seconds)
                    self._security_headers(response)
                    return response
                bucket.append(now)
        response = await call_next(request)
        self._security_headers(response)
        return response

    @staticmethod
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.environment.lower() in {"production", "prod"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
