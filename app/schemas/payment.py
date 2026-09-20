"""Payment schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import BaseSchema


class PaymentInitiateRequest(BaseSchema):
    consultation_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="INR", max_length=3)
    gateway_name: str = Field(default="razorpay", max_length=50)


class PaymentOut(BaseSchema):
    id: uuid.UUID
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    gateway_ref: str | None = None
    gateway_name: str | None = None
    idempotency_key: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class WebhookPayload(BaseSchema):
    """Generic webhook payload from payment gateway."""

    event: str
    payment_id: str
    consultation_id: str | None = None
    gateway_ref: str
    status: str
    amount: Decimal | None = None
    metadata: dict | None = None
