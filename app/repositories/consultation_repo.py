"""Consultation repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.consultation import Consultation, ConsultationNote
from app.repositories.base import BaseRepository


class ConsultationRepository(BaseRepository[Consultation]):
    model = Consultation

    async def get_by_idempotency_key(self, key: str) -> Consultation | None:
        result = await self.db.execute(
            select(Consultation)
            .where(Consultation.idempotency_key == key)
            .options(selectinload(Consultation.notes))
        )
        return result.scalar_one_or_none()

    async def get_with_details(self, consultation_id: UUID) -> Consultation | None:
        result = await self.db.execute(
            select(Consultation)
            .where(Consultation.id == consultation_id)
            .options(
                selectinload(Consultation.notes),
                selectinload(Consultation.prescription),
                selectinload(Consultation.payment),
                selectinload(Consultation.slot),
            )
        )
        return result.scalar_one_or_none()

    async def get_patient_consultations(
        self, patient_id: UUID, offset: int = 0, limit: int = 20
    ) -> list[Consultation]:
        result = await self.db.execute(
            select(Consultation)
            .where(Consultation.patient_id == patient_id)
            .options(
                selectinload(Consultation.slot),
                selectinload(Consultation.notes),
            )
            .order_by(Consultation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_doctor_consultations(
        self, doctor_id: UUID, status: str | None = None, offset: int = 0, limit: int = 20
    ) -> list[Consultation]:
        stmt = (
            select(Consultation)
            .where(Consultation.doctor_id == doctor_id)
            .options(
                selectinload(Consultation.slot),
                selectinload(Consultation.notes),
            )
            .order_by(Consultation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Consultation.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ConsultationNoteRepository(BaseRepository[ConsultationNote]):
    model = ConsultationNote

    async def get_by_consultation(self, consultation_id: UUID) -> list[ConsultationNote]:
        result = await self.db.execute(
            select(ConsultationNote)
            .where(ConsultationNote.consultation_id == consultation_id)
            .order_by(ConsultationNote.created_at)
        )
        return list(result.scalars().all())
