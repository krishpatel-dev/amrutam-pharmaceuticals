"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, unhandled_error_handler
from app.core.middleware import AuditLogMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware
from app.db.base import engine
from app.observability.logging_conf import setup_logging
from app.observability.tracing import setup_tracing

logger = structlog.get_logger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri=settings.REDIS_URL,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    # Startup
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_logs=settings.is_production,
    )
    logger.info(
        "application_starting",
        environment=settings.APP_ENV,
        version=settings.APP_VERSION,
    )

    if settings.OTLP_ENDPOINT:
        setup_tracing(app, engine, otlp_endpoint=settings.OTLP_ENDPOINT)
        logger.info("tracing_enabled", endpoint=settings.OTLP_ENDPOINT)

    yield

    # Shutdown
    await engine.dispose()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Telemedicine backend API for Amrutam — "
        "doctor search, consultation booking, prescriptions, and payments.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type]

    if settings.ENABLE_METRICS:
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/health", "/ready", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    app.include_router(api_v1_router)

    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/ready", tags=["Health"], include_in_schema=False, response_model=None)
    async def ready():  # type: ignore[return]
        """Readiness probe — check DB connectivity."""
        from fastapi import status as http_status

        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception as exc:
            return JSONResponse(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "database": str(exc)},
            )

    return app


app = create_app()
