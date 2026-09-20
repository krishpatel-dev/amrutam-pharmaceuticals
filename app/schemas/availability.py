"""Availability slot schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.schemas.common import BaseSchema


class SlotCreate(BaseSchema):
    start_time: datetime
    end_time: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    recurrence_rule: str | None = Field(default=None, max_length=255)

    @field_validator("start_time", "end_time")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware (include timezone info).")
        return v

    @model_validator(mode="after")
    def end_must_be_after_start(self) -> SlotCreate:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class SlotBulkCreate(BaseSchema):
    """Create multiple slots at once."""
    slots: list[SlotCreate] = Field(..., min_length=1, max_length=100)


class SlotOut(BaseSchema):
    id: uuid.UUID
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    is_booked: bool
    is_active: bool
    recurrence_rule: str | None = None
    created_at: datetime
