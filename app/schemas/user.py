"""User and UserProfile schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class ProfileOut(BaseSchema):
    first_name: str
    last_name: str
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    avatar_url: str | None = None
    full_name: str | None = None


class UserOut(BaseSchema):
    id: uuid.UUID
    email: EmailStr
    role: str
    is_active: bool
    is_email_verified: bool
    mfa_enabled: bool
    created_at: datetime
    profile: ProfileOut | None = None


class ProfileUpdateRequest(BaseSchema):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern="^(male|female|other|prefer_not_to_say)$")
    address: str | None = Field(default=None, max_length=500)


class AdminUserOut(UserOut):
    """Extended user view for admin endpoints (includes extra fields)."""

    updated_at: datetime


class UserStatusUpdateRequest(BaseSchema):
    is_active: bool
