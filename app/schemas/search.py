"""Search schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import BaseSchema


class DoctorSearchParams(BaseSchema):
    """Query parameters for doctor search endpoint."""

    q: str | None = Field(default=None, max_length=100, description="Name or keyword search")
    specialty: str | None = Field(default=None, max_length=150)
    min_fee: Decimal | None = Field(default=None, ge=Decimal("0"))
    max_fee: Decimal | None = Field(default=None, ge=Decimal("0"))
    min_rating: float | None = Field(default=None, ge=0.0, le=5.0)
    min_experience: int | None = Field(default=None, ge=0)
    available_from: datetime | None = None
    available_to: datetime | None = None
    language: str | None = Field(default=None, max_length=50)
    sort_by: str = Field(
        default="rating",
        pattern="^(rating|fee_asc|fee_desc|experience|consultations)$",
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
