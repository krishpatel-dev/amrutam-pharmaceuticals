"""Security utilities: JWT, password hashing, MFA (TOTP), and idempotency."""

from __future__ import annotations

import hashlib
import hmac
import io
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import pyotp
import qrcode
from jose import JWTError, jwt

from app.core.config import settings

_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt (rounds=12)."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


TokenType = dict[str, Any]


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_hex(16),  # JWT ID for revocation support
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived access JWT."""
    return _create_token(
        subject=user_id,
        token_type="access",  # nosec B106
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh JWT."""
    return _create_token(
        subject=user_id,
        token_type="refresh",  # nosec B106
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> TokenType:
    """Decode and validate a JWT. Raises JWTError if invalid or expired."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
    except JWTError:
        raise


def generate_mfa_secret() -> str:
    """Generate a new TOTP secret key (base32 encoded)."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Return the otpauth:// URI used to populate an authenticator app."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.MFA_ISSUER_NAME)


def generate_qr_code_bytes(otp_uri: str) -> bytes:
    """Generate a QR code PNG as raw bytes for the given OTP URI."""
    img = qrcode.make(otp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code. Allows 1 window (30 s) drift for clock skew."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_idempotency_key() -> str:
    """Generate a cryptographically secure idempotency key."""
    return secrets.token_urlsafe(32)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify a payment webhook signature with HMAC-SHA256. Returns True if valid."""
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def mask_sensitive(value: str, visible: int = 4) -> str:
    """Mask a sensitive string, showing only the last `visible` chars."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]
