"""Auth API router."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.core.dependencies import CurrentUserID, DBSession
from app.schemas.auth import (
    LoginRequest,
    MFAValidateRequest,
    MFAVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse, SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient or doctor account",
)
async def register(
    request: Request,
    body: RegisterRequest,
    db: DBSession,
) -> SuccessResponse:
    service = AuthService(db)
    user = await service.register(body, ip=_get_client_ip(request))
    return SuccessResponse(
        message="Registration successful. Please check your email to verify your account.",
        data=user.model_dump(mode="json"),
    )


@router.post(
    "/login",
    summary="Login with email and password",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: DBSession,
) -> dict:
    service = AuthService(db)
    result = await service.login(body, ip=_get_client_ip(request))
    return result if isinstance(result, dict) else result.model_dump()


@router.post(
    "/refresh",
    summary="Exchange refresh token for new access token",
)
async def refresh_token(
    body: RefreshRequest,
    db: DBSession,
) -> TokenResponse:
    service = AuthService(db)
    return await service.refresh_tokens(body.refresh_token)


@router.post(
    "/mfa/validate",
    summary="Complete MFA challenge to obtain tokens",
)
async def validate_mfa(
    request: Request,
    body: MFAValidateRequest,
    db: DBSession,
) -> TokenResponse:
    """Called after login when ``mfa_required=True`` is returned."""
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(body.email)
    if not user:
        from app.core.exceptions import InvalidCredentialsError
        raise InvalidCredentialsError()

    service = AuthService(db)
    return await service.validate_mfa(str(user.id), body.code, ip=_get_client_ip(request))


@router.post(
    "/mfa/setup",
    summary="Generate TOTP secret and QR code",
)
async def setup_mfa(
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = AuthService(db)
    result = await service.setup_mfa(user_id)
    return SuccessResponse(
        message="Scan the QR code with your authenticator app, then call /mfa/confirm.",
        data=result.model_dump(),
    )


@router.post(
    "/mfa/confirm",
    summary="Confirm TOTP code to enable MFA",
)
async def confirm_mfa(
    user_id: CurrentUserID,
    body: MFAVerifyRequest,
    db: DBSession,
) -> MessageResponse:
    service = AuthService(db)
    await service.confirm_mfa_setup(user_id, body.code)
    return MessageResponse(message="MFA has been successfully enabled on your account.")
