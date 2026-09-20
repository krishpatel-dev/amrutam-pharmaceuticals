"""Payments API router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, Request, status

from app.core.dependencies import CurrentUserID, DBSession, IdempotencyKey, RequirePatient
from app.schemas.common import SuccessResponse
from app.schemas.payment import PaymentInitiateRequest, WebhookPayload
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


def _get_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment for a consultation (patient only)",
    dependencies=[RequirePatient],
)
async def initiate_payment(
    request: Request,
    body: PaymentInitiateRequest,
    user_id: CurrentUserID,
    db: DBSession,
    idempotency_key: IdempotencyKey = None,
) -> SuccessResponse:
    service = PaymentService(db)
    payment = await service.initiate(
        patient_id=uuid.UUID(user_id),
        data=body,
        idempotency_key=idempotency_key,
        ip=_get_ip(request),
    )
    return SuccessResponse(
        message="Payment initiated.",
        data=payment.model_dump(mode="json"),
    )


@router.get(
    "/{payment_id}",
    summary="Get payment status",
)
async def get_payment(
    payment_id: uuid.UUID,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = PaymentService(db)
    payment = await service.get_payment(payment_id, uuid.UUID(user_id))
    return SuccessResponse(data=payment.model_dump(mode="json"))


@router.post(
    "/webhook",
    summary="Payment gateway webhook (internal use)",
)
async def payment_webhook(
    request: Request,
    body: WebhookPayload,
    db: DBSession,
    x_gateway_signature: str = Header(alias="X-Gateway-Signature", default=""),
) -> SuccessResponse:
    """
    Receives payment events from the payment gateway.
    Signature verified via HMAC-SHA256 before processing.
    """
    payload_bytes = await request.body()
    service = PaymentService(db)
    payment = await service.process_webhook(payload_bytes, x_gateway_signature, body)
    return SuccessResponse(
        message="Webhook processed.",
        data=payment.model_dump(mode="json"),
    )
