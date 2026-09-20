"""Booking service — concurrency-safe slot reservation with idempotency."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.exceptions import (
    DoctorNotVerifiedError,
    ForbiddenError,
    NotFoundError,
    SlotInPastError,
    SlotUnavailableError,
)
from app.core.security import generate_idempotency_key
from app.models.consultation import ConsultationStatus
from app.repositories.audit_repo import AuditRepository
from app.repositories.availability_repo import AvailabilityRepository
from app.repositories.consultation_repo import (
    ConsultationNoteRepository,
    ConsultationRepository,
)
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.consultation import (
    BookingRequest,
    ConsultationNoteCreate,
    ConsultationOut,
)

logger = structlog.get_logger(__name__)


class BookingService:
    def __init__(self, db: AsyncSession) -> None:
        self._slot_repo = AvailabilityRepository(db)
        self._consult_repo = ConsultationRepository(db)
        self._note_repo = ConsultationNoteRepository(db)
        self._doctor_repo = DoctorRepository(db)
        self._audit_repo = AuditRepository(db)

    async def book_consultation(
        self,
        patient_id: UUID,
        data: BookingRequest,
        idempotency_key: str | None = None,
        ip: str | None = None,
    ) -> ConsultationOut:
        """
        Book a consultation for a patient.

        Idempotency: if the same ``idempotency_key`` is reused, the existing
        consultation record is returned without creating a duplicate.

        Concurrency: uses ``SELECT FOR UPDATE`` on the slot row to prevent
        two concurrent requests from booking the same slot.
        """
        key = idempotency_key or generate_idempotency_key()
        existing = await self._consult_repo.get_by_idempotency_key(key)
        if existing:
            logger.info("booking_idempotent_hit", key=key)
            return ConsultationOut.model_validate(existing)

        slot = await self._slot_repo.lock_slot_for_booking(data.slot_id)
        if slot is None:
            raise SlotUnavailableError()

        now = datetime.now(UTC)
        slot_start = (
            slot.start_time
            if slot.start_time.tzinfo
            else slot.start_time.replace(tzinfo=UTC)
        )
        if slot_start < now:
            raise SlotInPastError()

        doctor = await self._doctor_repo.get_by_id(slot.doctor_id)
        if not doctor or not doctor.is_verified:
            raise DoctorNotVerifiedError()

        await self._slot_repo.mark_booked(slot)

        consultation = await self._consult_repo.create(
            patient_id=patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id,
            status=ConsultationStatus.SCHEDULED,
            chief_complaint=data.chief_complaint,
            scheduled_at=slot.start_time,
            idempotency_key=key,
        )
        set_committed_value(consultation, "notes", [])

        await self._audit_repo.log(
            action="consultation_booked",
            user_id=patient_id,
            resource_type="consultation",
            resource_id=str(consultation.id),
            ip_address=ip,
            extra={"slot_id": str(data.slot_id), "doctor_id": str(slot.doctor_id)},
        )

        logger.info(
            "consultation_booked",
            consultation_id=str(consultation.id),
            patient_id=str(patient_id),
        )
        return ConsultationOut.model_validate(consultation)

    async def start_consultation(
        self,
        consultation_id: UUID,
        doctor_id: UUID,
        doctor_user_id: UUID | None = None,
    ) -> ConsultationOut:
        """Mark a consultation as in-progress (doctor only)."""
        consultation = await self._consult_repo.get_with_details(consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")

        if consultation.doctor_id != doctor_id:
            raise ForbiddenError("You are not the assigned doctor for this consultation.")

        if consultation.status != ConsultationStatus.SCHEDULED:
            raise ForbiddenError(
                f"Cannot start a consultation with status '{consultation.status}'."
            )

        updated = await self._consult_repo.update(
            consultation,
            status=ConsultationStatus.IN_PROGRESS,
            started_at=datetime.now(UTC),
        )

        auth_user_id = doctor_user_id
        if auth_user_id is None:
            doc = await self._doctor_repo.get_by_id(doctor_id)
            auth_user_id = doc.user_id if doc else None

        await self._audit_repo.log(
            action="consultation_started",
            user_id=auth_user_id,
            resource_type="consultation",
            resource_id=str(consultation_id),
        )
        return ConsultationOut.model_validate(updated)

    async def end_consultation(
        self,
        consultation_id: UUID,
        doctor_id: UUID,
        doctor_user_id: UUID | None = None,
    ) -> ConsultationOut:
        """Mark a consultation as completed (doctor only)."""
        consultation = await self._consult_repo.get_with_details(consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")

        if consultation.doctor_id != doctor_id:
            raise ForbiddenError("You are not the assigned doctor.")

        if consultation.status != ConsultationStatus.IN_PROGRESS:
            raise ForbiddenError("Consultation is not in progress.")

        updated = await self._consult_repo.update(
            consultation,
            status=ConsultationStatus.COMPLETED,
            ended_at=datetime.now(UTC),
        )

        auth_user_id = doctor_user_id
        if auth_user_id is None:
            doc = await self._doctor_repo.get_by_id(doctor_id)
            auth_user_id = doc.user_id if doc else None

        await self._audit_repo.log(
            action="consultation_completed",
            user_id=auth_user_id,
            resource_type="consultation",
            resource_id=str(consultation_id),
        )
        return ConsultationOut.model_validate(updated)

    async def cancel_consultation(
        self,
        consultation_id: UUID,
        requester_id: UUID,
        reason: str | None = None,
    ) -> ConsultationOut:
        """Cancel a consultation (patient or doctor can cancel)."""
        consultation = await self._consult_repo.get_with_details(consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")

        if consultation.patient_id != requester_id and consultation.doctor_id != requester_id:
            raise ForbiddenError("You are not a participant of this consultation.")

        if consultation.status in (
            ConsultationStatus.COMPLETED,
            ConsultationStatus.CANCELLED,
        ):
            raise ForbiddenError(f"Cannot cancel a '{consultation.status}' consultation.")

        # Release the slot
        slot = await self._slot_repo.get_by_id(consultation.slot_id)
        if slot:
            await self._slot_repo.update(slot, is_booked=False)

        updated = await self._consult_repo.update(
            consultation,
            status=ConsultationStatus.CANCELLED,
            cancellation_reason=reason,
        )
        await self._audit_repo.log(
            action="consultation_cancelled",
            user_id=requester_id,
            resource_type="consultation",
            resource_id=str(consultation_id),
            detail=reason,
        )
        return ConsultationOut.model_validate(updated)

    async def add_note(
        self,
        consultation_id: UUID,
        author_id: UUID,
        data: ConsultationNoteCreate,
    ) -> ConsultationOut:
        """Add a clinical note to an in-progress consultation."""
        consultation = await self._consult_repo.get_with_details(consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")

        if consultation.doctor_id != author_id:
            raise ForbiddenError("Only the assigned doctor can add notes.")

        if consultation.status != ConsultationStatus.IN_PROGRESS:
            raise ForbiddenError("Notes can only be added during an active consultation.")

        await self._note_repo.create(
            consultation_id=consultation_id,
            author_id=author_id,
            content=data.content,
        )

        # Refresh to include new note
        updated = await self._consult_repo.get_with_details(consultation_id)
        return ConsultationOut.model_validate(updated)
