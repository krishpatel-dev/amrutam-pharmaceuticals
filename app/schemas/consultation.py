"""Consultation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class BookingRequest(BaseSchema):
    slot_id: uuid.UUID
    chief_complaint: str | None = Field(default=None, max_length=1000)


class ConsultationNoteCreate(BaseSchema):
    content: str = Field(..., min_length=1, max_length=5000)


class ConsultationNoteOut(BaseSchema):
    id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime


class ConsultationOut(BaseSchema):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    slot_id: uuid.UUID
    status: str
    chief_complaint: str | None = None
    cancellation_reason: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    idempotency_key: str
    created_at: datetime
    notes: list[ConsultationNoteOut] = []


class CancelConsultationRequest(BaseSchema):
    reason: str | None = Field(default=None, max_length=500)
