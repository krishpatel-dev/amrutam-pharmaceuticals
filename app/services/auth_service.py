"""Authentication service — registration, login, MFA, token refresh."""

from __future__ import annotations

import base64
import uuid

import structlog
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidMFACodeError,
    TokenExpiredError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_mfa_secret,
    generate_qr_code_bytes,
    get_totp_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    MFASetupResponse,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserOut

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._user_repo = UserRepository(db)
        self._audit_repo = AuditRepository(db)

    async def register(
        self, data: RegisterRequest, ip: str | None = None
    ) -> UserOut:
        """Register a new user (patient or doctor)."""
        if await self._user_repo.email_exists(data.email):
            raise DuplicateEmailError()

        hashed = hash_password(data.password)
        user = await self._user_repo.create_with_profile(
            email=data.email,
            hashed_password=hashed,
            role=data.role,
            first_name=data.first_name,
            last_name=data.last_name,
        )

        await self._audit_repo.log(
            action="user_registered",
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            ip_address=ip,
            extra={"role": data.role},
        )

        logger.info("user_registered", user_id=str(user.id), role=data.role)
        return UserOut.model_validate(user)

    async def login(
        self, data: LoginRequest, ip: str | None = None
    ) -> TokenResponse | dict:
        """Authenticate a user. Returns tokens directly, or mfa_required=True if MFA is on."""
        user = await self._user_repo.get_by_email(data.email)

        if not user or not verify_password(data.password, user.hashed_password):
            await self._audit_repo.log(
                action="login_failed",
                ip_address=ip,
                outcome="failure",
                detail=f"Invalid credentials for {data.email}",
            )
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError("Account is deactivated.")

        await self._audit_repo.log(
            action="login_success",
            user_id=user.id,
            ip_address=ip,
            resource_type="user",
            resource_id=str(user.id),
        )

        if user.mfa_enabled:
            # Signal to the caller that MFA validation is needed
            logger.info("mfa_challenge_issued", user_id=str(user.id))
            return {"mfa_required": True, "user_id": str(user.id)}

        return self._build_token_response(user)

    async def validate_mfa(
        self, user_id: str, code: str, ip: str | None = None
    ) -> TokenResponse:
        """Validate TOTP code and issue tokens."""
        user = await self._user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.mfa_enabled or not user.mfa_secret:
            raise UnauthorizedError("MFA is not set up for this account.")

        if not verify_totp(user.mfa_secret, code):
            await self._audit_repo.log(
                action="mfa_failed",
                user_id=user.id,
                ip_address=ip,
                outcome="failure",
            )
            raise InvalidMFACodeError()

        await self._audit_repo.log(
            action="mfa_success", user_id=user.id, ip_address=ip
        )
        return self._build_token_response(user)

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Exchange a valid refresh token for new access + refresh tokens."""
        try:
            payload = decode_token(refresh_token)
        except JWTError as exc:
            raise TokenExpiredError("Refresh token is invalid or expired.") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Expected a refresh token.")

        user = await self._user_repo.get_by_id(uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or deactivated.")

        return self._build_token_response(user)

    async def setup_mfa(self, user_id: str) -> MFASetupResponse:
        """Generate a new TOTP secret and return QR code for the user."""
        user = await self._user_repo.get_with_profile(uuid.UUID(user_id))
        if not user:
            raise UnauthorizedError()

        secret = generate_mfa_secret()
        otp_uri = get_totp_uri(secret, user.email)
        qr_bytes = generate_qr_code_bytes(otp_uri)
        qr_b64 = base64.b64encode(qr_bytes).decode()

        # Store secret temporarily — only confirmed on /mfa/verify
        await self._user_repo.update(user, mfa_secret=secret)

        return MFASetupResponse(
            secret=secret,
            qr_code_url=f"data:image/png;base64,{qr_b64}",
            manual_entry_key=secret,
        )

    async def confirm_mfa_setup(self, user_id: str, code: str) -> None:
        """Verify the TOTP code and enable MFA on the account."""
        user = await self._user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.mfa_secret:
            raise UnauthorizedError("MFA setup not initiated.")

        if not verify_totp(user.mfa_secret, code):
            raise InvalidMFACodeError()

        await self._user_repo.update(user, mfa_enabled=True)
        await self._audit_repo.log(
            action="mfa_enabled",
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
        )

    @staticmethod
    def _build_token_response(user) -> TokenResponse:
        from app.core.config import settings

        access_token = create_access_token(str(user.id), user.role)
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
