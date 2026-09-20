"""Payment service with idempotency and webhook processing."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    PaymentAlreadyProcessedError,
)
from app.core.security import generate_idempotency_key, verify_webhook_signature
from app.models.payment import PaymentStatus
from app.repositories.audit_repo import AuditRepository
from app.repositories.consultation_repo import ConsultationRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.payment import PaymentInitiateRequest, PaymentOut, WebhookPayload

logger = structlog.get_logger(__name__)


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self._payment_repo = PaymentRepository(db)
        self._consult_repo = ConsultationRepository(db)
        self._audit_repo = AuditRepository(db)

    async def initiate(
        self,
        patient_id: UUID,
        data: PaymentInitiateRequest,
        idempotency_key: str | None = None,
        ip: str | None = None,
    ) -> PaymentOut:
        """
        Create or retrieve an idempotent payment record.

        If the same idempotency_key is presented, the existing payment is
        returned unchanged — preventing duplicate charges on retries.
        """
        key = idempotency_key or generate_idempotency_key()

        existing = await self._payment_repo.get_by_idempotency_key(key)
        if existing:
            logger.info("payment_idempotent_hit", key=key, payment_id=str(existing.id))
            return PaymentOut.model_validate(existing)

        consultation = await self._consult_repo.get_by_id(data.consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")
        if consultation.patient_id != patient_id:
            raise ForbiddenError("You can only initiate payment for your own consultations.")

        existing_payment = await self._payment_repo.get_by_consultation_id(data.consultation_id)
        if existing_payment and existing_payment.status == PaymentStatus.COMPLETED:
            raise PaymentAlreadyProcessedError()

        payment = await self._payment_repo.create(
            consultation_id=data.consultation_id,
            patient_id=patient_id,
            amount=data.amount,
            currency=data.currency,
            gateway_name=data.gateway_name,
            status=PaymentStatus.PENDING,
            idempotency_key=key,
        )

        await self._audit_repo.log(
            action="payment_initiated",
            user_id=patient_id,
            resource_type="payment",
            resource_id=str(payment.id),
            ip_address=ip,
            extra={
                "consultation_id": str(data.consultation_id),
                "amount": str(data.amount),
                "currency": data.currency,
            },
        )

        logger.info(
            "payment_initiated",
            payment_id=str(payment.id),
            amount=str(data.amount),
        )
        return PaymentOut.model_validate(payment)

    async def process_webhook(
        self, payload_bytes: bytes, signature: str, payload: WebhookPayload
    ) -> PaymentOut:
        """
        Process a signed payment gateway webhook event.

        Validates the HMAC signature first, then transitions the payment
        to completed or failed based on the event type.
        """
        if not verify_webhook_signature(payload_bytes, signature, settings.PAYMENT_WEBHOOK_SECRET):
            logger.warning("webhook_invalid_signature", event=payload.event)
            raise ForbiddenError("Invalid webhook signature.")

        payment = await self._payment_repo.get_by_gateway_ref(payload.gateway_ref)

        # Idempotency: look up by gateway_ref if not found
        if not payment and payload.consultation_id:
            consultation = await self._consult_repo.get_by_id(
                UUID(payload.consultation_id)
            )
            if consultation:
                payment = await self._payment_repo.get_by_consultation_id(consultation.id)

        if not payment:
            raise NotFoundError("Payment record not found for this webhook.")

        if payment.status == PaymentStatus.COMPLETED:
            logger.info("webhook_already_processed", payment_id=str(payment.id))
            return PaymentOut.model_validate(payment)

        if payload.status in ("success", "captured"):
            updated = await self._payment_repo.update(
                payment,
                status=PaymentStatus.COMPLETED,
                gateway_ref=payload.gateway_ref,
            )
            await self._audit_repo.log(
                action="payment_completed",
                resource_type="payment",
                resource_id=str(payment.id),
                extra={"gateway_ref": payload.gateway_ref},
            )
        else:
            updated = await self._payment_repo.update(
                payment,
                status=PaymentStatus.FAILED,
                failure_reason=payload.status,
            )
            await self._audit_repo.log(
                action="payment_failed",
                resource_type="payment",
                resource_id=str(payment.id),
                outcome="failure",
                detail=payload.status,
            )

        logger.info(
            "webhook_processed",
            payment_id=str(payment.id),
            new_status=updated.status,
        )
        return PaymentOut.model_validate(updated)

    async def get_payment(self, payment_id: UUID, requester_id: UUID) -> PaymentOut:
        payment = await self._payment_repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("Payment not found.")
        if payment.patient_id != requester_id:
            raise ForbiddenError("Access denied.")
        return PaymentOut.model_validate(payment)
