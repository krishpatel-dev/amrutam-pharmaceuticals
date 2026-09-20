"""Prescription schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class MedicationCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    route: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)


class MedicationOut(BaseSchema):
    id: uuid.UUID
    name: str
    dosage: str
    frequency: str
    duration_days: int | None = None
    route: str | None = None
    notes: str | None = None


class PrescriptionCreate(BaseSchema):
    consultation_id: uuid.UUID
    diagnosis: str | None = Field(default=None, max_length=1000)
    instructions: str | None = Field(default=None, max_length=2000)
    follow_up_date: datetime | None = None
    medications: list[MedicationCreate] = Field(..., min_length=1, max_length=20)


class PrescriptionOut(BaseSchema):
    id: uuid.UUID
    consultation_id: uuid.UUID
    issued_by: uuid.UUID
    diagnosis: str | None = None
    instructions: str | None = None
    follow_up_date: datetime | None = None
    is_active: bool
    issued_at: datetime
    medications: list[MedicationOut] = []
