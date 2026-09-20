"""Doctor repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.user import User, UserProfile
from app.repositories.base import BaseRepository
from app.schemas.search import DoctorSearchParams


class DoctorRepository(BaseRepository[Doctor]):
    model = Doctor

    async def get_by_user_id(self, user_id: UUID) -> Doctor | None:
        result = await self.db.execute(
            select(Doctor)
            .where(Doctor.user_id == user_id)
            .options(selectinload(Doctor.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def get_with_user(self, doctor_id: UUID) -> Doctor | None:
        result = await self.db.execute(
            select(Doctor)
            .where(Doctor.id == doctor_id)
            .options(selectinload(Doctor.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def license_exists(self, license_number: str) -> bool:
        result = await self.db.execute(
            select(Doctor.id).where(Doctor.license_number == license_number)
        )
        return result.scalar_one_or_none() is not None

    async def search(self, params: DoctorSearchParams) -> tuple[list[Doctor], int]:
        """
        Multi-filter doctor search with pagination.
        Returns (results, total_count).
        """
        from sqlalchemy import func, or_

        stmt = (
            select(Doctor)
            .join(Doctor.user)
            .join(User.profile, isouter=True)
            .where(Doctor.is_verified == True)  # Only verified doctors # noqa: E712
        )

        # Filters
        if params.specialty:
            stmt = stmt.where(Doctor.specialty.ilike(f"%{params.specialty}%"))
        if params.min_fee is not None:
            stmt = stmt.where(Doctor.consultation_fee >= params.min_fee)
        if params.max_fee is not None:
            stmt = stmt.where(Doctor.consultation_fee <= params.max_fee)
        if params.min_rating is not None:
            stmt = stmt.where(Doctor.rating >= params.min_rating)
        if params.min_experience is not None:
            stmt = stmt.where(Doctor.years_experience >= params.min_experience)
        if params.language:
            stmt = stmt.where(Doctor.languages.ilike(f"%{params.language}%"))
        if params.q:
            search_term = f"%{params.q}%"
            stmt = stmt.where(
                or_(
                    UserProfile.first_name.ilike(search_term),
                    UserProfile.last_name.ilike(search_term),
                    Doctor.specialty.ilike(search_term),
                    Doctor.bio.ilike(search_term),
                )
            )

        # Availability filter
        if params.available_from and params.available_to:
            from app.models.availability import AvailabilitySlot

            stmt = stmt.where(
                Doctor.id.in_(
                    select(AvailabilitySlot.doctor_id).where(
                        and_(
                            AvailabilitySlot.start_time >= params.available_from,
                            AvailabilitySlot.end_time <= params.available_to,
                            AvailabilitySlot.is_booked == False,  # noqa: E712
                            AvailabilitySlot.is_active == True,   # noqa: E712
                        )
                    )
                )
            )

        # Sorting
        sort_map = {
            "rating": Doctor.rating.desc(),
            "fee_asc": Doctor.consultation_fee.asc(),
            "fee_desc": Doctor.consultation_fee.desc(),
            "experience": Doctor.years_experience.desc(),
            "consultations": Doctor.total_consultations.desc(),
        }
        stmt = stmt.order_by(sort_map.get(params.sort_by, Doctor.rating.desc()))

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginate
        offset = (params.page - 1) * params.page_size
        stmt = (
            stmt.offset(offset)
            .limit(params.page_size)
            .options(selectinload(Doctor.user).selectinload(User.profile))
        )
        result = await self.db.execute(stmt)
        doctors = list(result.scalars().unique().all())

        return doctors, total
