"""FastAPI dependency injection: DB sessions, auth, RBAC, idempotency."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import decode_token
from app.db.base import get_db

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict:
    """Extract and validate JWT from Authorization header."""
    if credentials is None:
        raise UnauthorizedError("Missing Bearer token.")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid or expired token: {exc}") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Expected an access token.")
    return payload


TokenPayload = Annotated[dict, Depends(_get_token_payload)]


async def get_current_user_id(payload: TokenPayload) -> str:
    """Return the user ID from the validated JWT payload."""
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token is missing subject claim.")
    return user_id


async def get_current_user_role(payload: TokenPayload) -> str:
    """Return the role from the validated JWT payload."""
    role: str | None = payload.get("role")
    if not role:
        raise UnauthorizedError("Token is missing role claim.")
    return role


CurrentUserID = Annotated[str, Depends(get_current_user_id)]
CurrentUserRole = Annotated[str, Depends(get_current_user_role)]


def require_roles(*allowed_roles: str):
    """Returns a FastAPI dependency that raises 403 if the caller's role isn't in allowed_roles."""

    async def _check(role: CurrentUserRole) -> str:
        if role not in allowed_roles:
            raise ForbiddenError(
                f"This endpoint requires one of the following roles: {', '.join(allowed_roles)}."
            )
        return role

    return Depends(_check)


# Convenience shortcuts
RequirePatient = require_roles("patient")
RequireDoctor = require_roles("doctor")
RequireAdmin = require_roles("admin")
RequireDoctorOrAdmin = require_roles("doctor", "admin")
RequireAny = require_roles("patient", "doctor", "admin")


async def get_idempotency_key(
    x_idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
) -> str | None:
    """Extract optional idempotency key from request headers."""
    return x_idempotency_key


IdempotencyKey = Annotated[str | None, Depends(get_idempotency_key)]


class PaginationParams:
    """Common pagination query parameters."""

    def __init__(self, page: int = 1, page_size: int = 20) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)
        self.offset = (self.page - 1) * self.page_size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
