"""Availability slot repository with pessimistic locking."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select

from app.models.availability import AvailabilitySlot
from app.repositories.base import BaseRepository


class AvailabilityRepository(BaseRepository[AvailabilitySlot]):
    model = AvailabilitySlot

    async def get_doctor_slots(
        self,
        doctor_id: UUID,
        from_time: datetime | None = None,
        only_available: bool = True,
    ) -> list[AvailabilitySlot]:
        stmt = select(AvailabilitySlot).where(
            AvailabilitySlot.doctor_id == doctor_id,
            AvailabilitySlot.is_active == True,  # noqa: E712
        )
        if only_available:
            stmt = stmt.where(AvailabilitySlot.is_booked == False)  # noqa: E712
        if from_time:
            stmt = stmt.where(AvailabilitySlot.start_time >= from_time)
        stmt = stmt.order_by(AvailabilitySlot.start_time)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def lock_slot_for_booking(self, slot_id: UUID) -> AvailabilitySlot | None:
        """
        Acquire a pessimistic row-level lock on the slot.

        This prevents two concurrent requests from booking the same slot.
        Must be called inside an active transaction.

        Returns None if the slot does not exist, is already booked, or inactive.
        """
        result = await self.db.execute(
            select(AvailabilitySlot)
            .where(
                and_(
                    AvailabilitySlot.id == slot_id,
                    AvailabilitySlot.is_booked == False,  # noqa: E712
                    AvailabilitySlot.is_active == True,   # noqa: E712
                )
            )
            .with_for_update()  # ← Pessimistic lock
        )
        return result.scalar_one_or_none()

    async def mark_booked(self, slot: AvailabilitySlot) -> AvailabilitySlot:
        slot.is_booked = True
        await self.db.flush()
        return slot
