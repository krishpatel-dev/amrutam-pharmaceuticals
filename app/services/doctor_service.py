"""Doctor management service."""

from __future__ import annotations

from datetime import UTC
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.repositories.audit_repo import AuditRepository
from app.repositories.doctor_repo import DoctorRepository
from app.repositories.user_repo import UserRepository
from app.schemas.doctor import DoctorCreate, DoctorOut, DoctorUpdateRequest

logger = structlog.get_logger(__name__)


class DoctorService:
    def __init__(self, db: AsyncSession) -> None:
        self._doctor_repo = DoctorRepository(db)
        self._user_repo = UserRepository(db)
        self._audit_repo = AuditRepository(db)

    async def create_doctor_profile(
        self, user_id: UUID, data: DoctorCreate
    ) -> DoctorOut:
        """Create a doctor profile for a user with the 'doctor' role."""
        user = await self._user_repo.get_with_profile(user_id)
        if not user or user.role != "doctor":
            raise ForbiddenError("Only users with the 'doctor' role can create a doctor profile.")

        if await self._doctor_repo.get_by_user_id(user_id):
            raise ConflictError("Doctor profile already exists.")

        if await self._doctor_repo.license_exists(data.license_number):
            raise ConflictError("A doctor with this license number already exists.")

        doctor = await self._doctor_repo.create(
            user_id=user_id,
            specialty=data.specialty,
            license_number=data.license_number,
            bio=data.bio,
            years_experience=data.years_experience,
            consultation_fee=data.consultation_fee,
            languages=data.languages,
        )

        await self._audit_repo.log(
            action="doctor_profile_created",
            user_id=user_id,
            resource_type="doctor",
            resource_id=str(doctor.id),
        )

        # Reload with user profile
        doctor = await self._doctor_repo.get_with_user(doctor.id)  # type: ignore[assignment]
        return self._to_out(doctor)

    async def get_doctor(self, doctor_id: UUID) -> DoctorOut:
        doctor = await self._doctor_repo.get_with_user(doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found.")
        return self._to_out(doctor)

    async def get_my_profile(self, user_id: UUID) -> DoctorOut:
        doctor = await self._doctor_repo.get_by_user_id(user_id)
        if not doctor:
            raise NotFoundError("Doctor profile not found.")
        return self._to_out(doctor)

    async def update_profile(
        self, user_id: UUID, data: DoctorUpdateRequest
    ) -> DoctorOut:
        doctor = await self._doctor_repo.get_by_user_id(user_id)
        if not doctor:
            raise NotFoundError("Doctor profile not found.")

        updates = data.model_dump(exclude_none=True)
        updated = await self._doctor_repo.update(doctor, **updates)
        return self._to_out(updated)

    async def verify_doctor(
        self, doctor_id: UUID, is_verified: bool, admin_id: UUID
    ) -> DoctorOut:
        """Admin action: verify or reject a doctor."""
        from datetime import datetime

        doctor = await self._doctor_repo.get_with_user(doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found.")

        updated = await self._doctor_repo.update(
            doctor,
            is_verified=is_verified,
            verified_by=admin_id,
            verified_at=datetime.now(UTC) if is_verified else None,
        )

        await self._audit_repo.log(
            action="doctor_verified" if is_verified else "doctor_rejected",
            user_id=admin_id,
            resource_type="doctor",
            resource_id=str(doctor_id),
        )
        return self._to_out(updated)

    @staticmethod
    def _to_out(doctor) -> DoctorOut:
        from app.schemas.user import ProfileOut

        profile_out = None
        if doctor.user and doctor.user.profile:
            p = doctor.user.profile
            profile_out = ProfileOut(
                first_name=p.first_name,
                last_name=p.last_name,
                phone=p.phone,
                date_of_birth=p.date_of_birth,
                gender=p.gender,
                address=p.address,
                avatar_url=p.avatar_url,
                full_name=p.full_name,
            )
        return DoctorOut(
            id=doctor.id,
            user_id=doctor.user_id,
            specialty=doctor.specialty,
            license_number=doctor.license_number,
            bio=doctor.bio,
            years_experience=doctor.years_experience,
            consultation_fee=doctor.consultation_fee,
            languages=doctor.languages,
            is_verified=doctor.is_verified,
            rating=doctor.rating,
            total_consultations=doctor.total_consultations,
            total_reviews=doctor.total_reviews,
            created_at=doctor.created_at,
            profile=profile_out,
        )
