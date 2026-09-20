"""ASGI middlewares: request ID injection, audit logging, security headers."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

# HTTP methods that mutate state — these are audited
_MUTABLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique request ID into every request/response cycle.

    - Reads ``X-Request-ID`` from incoming headers (forwarded proxies).
    - If absent, generates a new UUID4.
    - Stores on ``request.state.request_id`` for downstream access.
    - Echoes back in the ``X-Request-ID`` response header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind to structlog context for the duration of this request
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add OWASP-recommended security headers to every response.

    Headers added:
    - ``Strict-Transport-Security`` — enforce HTTPS
    - ``X-Content-Type-Options`` — prevent MIME sniffing
    - ``X-Frame-Options`` — prevent clickjacking
    - ``Referrer-Policy`` — limit referrer leakage
    - ``Permissions-Policy`` — disable browser features
    - ``Cache-Control`` — prevent caching of API responses
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Skip adding headers to metrics/health endpoints to avoid noise
        if request.url.path in {"/metrics", "/health", "/ready"}:
            return response

        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Log every mutating HTTP request with timing and outcome.

    Captured fields:
    - ``method``, ``path``, ``query``
    - ``status_code``, ``duration_ms``
    - ``request_id``, ``user_agent``, ``client_ip``

    Note: Body content is intentionally NOT logged to avoid leaking PHI/PII.
    The detailed audit trail is written by individual service methods.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if request.method in _MUTABLE_METHODS:
            client_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else "unknown")
            )
            log = logger.bind(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=request.headers.get("User-Agent", ""),
                request_id=getattr(request.state, "request_id", ""),
            )
            if response.status_code >= 500:
                log.error("request_error")
            elif response.status_code >= 400:
                log.warning("request_client_error")
            else:
                log.info("request_completed")

        return response
