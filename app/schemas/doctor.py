"""Doctor schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.user import ProfileOut


class DoctorCreate(BaseSchema):
    specialty: str = Field(..., min_length=2, max_length=150)
    license_number: str = Field(..., min_length=3, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    years_experience: int = Field(default=0, ge=0, le=60)
    consultation_fee: Decimal = Field(..., ge=0, decimal_places=2)
    languages: str | None = Field(default=None, max_length=255)


class DoctorUpdateRequest(BaseSchema):
    specialty: str | None = Field(default=None, min_length=2, max_length=150)
    bio: str | None = Field(default=None, max_length=2000)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    consultation_fee: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    languages: str | None = None


class DoctorOut(BaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    specialty: str
    license_number: str
    bio: str | None = None
    years_experience: int
    consultation_fee: Decimal
    languages: str | None = None
    is_verified: bool
    rating: float
    total_consultations: int
    total_reviews: int
    created_at: datetime

    # Nested profile from user relation (populated in service layer)
    profile: ProfileOut | None = None


class DoctorPublicOut(BaseSchema):
    """Public-facing doctor card (no sensitive fields)."""

    id: uuid.UUID
    specialty: str
    bio: str | None = None
    years_experience: int
    consultation_fee: Decimal
    languages: str | None = None
    rating: float
    total_consultations: int
    total_reviews: int
    profile: ProfileOut | None = None


class DoctorVerifyRequest(BaseSchema):
    is_verified: bool
    reason: str | None = Field(default=None, max_length=500)
