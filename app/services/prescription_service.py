"""Prescription service."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.consultation import ConsultationStatus
from app.models.prescription import Medication, Prescription
from app.repositories.audit_repo import AuditRepository
from app.repositories.consultation_repo import ConsultationRepository
from app.schemas.prescription import PrescriptionCreate, PrescriptionOut

logger = structlog.get_logger(__name__)


class PrescriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self._consult_repo = ConsultationRepository(db)
        self._audit_repo = AuditRepository(db)
        self._db = db

    async def issue_prescription(
        self, doctor_user_id: UUID, data: PrescriptionCreate
    ) -> PrescriptionOut:
        """Issue a prescription for a completed or in-progress consultation."""
        from app.repositories.doctor_repo import DoctorRepository

        doctor = await DoctorRepository(self._db).get_by_user_id(doctor_user_id)
        if not doctor:
            raise ForbiddenError("Doctor profile not found.")

        consultation = await self._consult_repo.get_with_details(data.consultation_id)
        if not consultation:
            raise NotFoundError("Consultation not found.")

        if consultation.doctor_id != doctor.id:
            raise ForbiddenError("You are not the assigned doctor for this consultation.")

        if consultation.status not in (
            ConsultationStatus.IN_PROGRESS,
            ConsultationStatus.COMPLETED,
        ):
            raise ForbiddenError(
                "Prescriptions can only be issued for in-progress or completed consultations."
            )

        if consultation.prescription:
            raise ConflictError("A prescription has already been issued for this consultation.")

        prescription = Prescription(
            consultation_id=data.consultation_id,
            issued_by=doctor_user_id,
            diagnosis=data.diagnosis,
            instructions=data.instructions,
            follow_up_date=data.follow_up_date,
        )
        self._db.add(prescription)
        await self._db.flush()
        await self._db.refresh(prescription)

        # Add medications
        for med_data in data.medications:
            med = Medication(
                prescription_id=prescription.id,
                name=med_data.name,
                dosage=med_data.dosage,
                frequency=med_data.frequency,
                duration_days=med_data.duration_days,
                route=med_data.route,
                notes=med_data.notes,
            )
            self._db.add(med)

        await self._db.flush()
        await self._db.refresh(prescription)

        await self._audit_repo.log(
            action="prescription_issued",
            user_id=doctor_user_id,
            resource_type="prescription",
            resource_id=str(prescription.id),
            extra={"consultation_id": str(data.consultation_id)},
        )

        return PrescriptionOut.model_validate(prescription)

    async def get_prescription(
        self, prescription_id: UUID, requester_id: UUID
    ) -> PrescriptionOut:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self._db.execute(
            select(Prescription)
            .where(Prescription.id == prescription_id)
            .options(selectinload(Prescription.medications))
        )
        prescription = result.scalar_one_or_none()
        if not prescription:
            raise NotFoundError("Prescription not found.")

        # Verify requester is the patient or doctor
        consultation = await self._consult_repo.get_by_id(prescription.consultation_id)
        if (
            consultation
            and consultation.patient_id != requester_id
            and prescription.issued_by != requester_id
        ):
            raise ForbiddenError("Access denied.")

        return PrescriptionOut.model_validate(prescription)
