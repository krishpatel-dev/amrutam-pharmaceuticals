"""Auth request/response schemas."""

from __future__ import annotations

import re

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema


class RegisterRequest(BaseSchema):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="patient", pattern="^(patient|doctor)$")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce strong password: uppercase, lowercase, digit, special char."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class MFAValidateRequest(BaseSchema):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseSchema):
    refresh_token: str


class MFASetupResponse(BaseSchema):
    secret: str
    qr_code_url: str  # data:image/png;base64,... for frontend display
    manual_entry_key: str


class MFAVerifyRequest(BaseSchema):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class PartialLoginResponse(BaseSchema):
    """Returned when MFA is required after successful password check."""

    mfa_required: bool = True
    message: str = "Please complete MFA verification."
