"""AvailabilitySlot ORM model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AvailabilitySlot(Base):
    """
    A time slot that a doctor makes available for consultation booking.

    ``is_booked`` is set to True atomically by the booking service using
    pessimistic locking (SELECT FOR UPDATE) to prevent race conditions.
    """

    __tablename__ = "availability_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional recurrence rule (iCal RRULE format, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR")
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    doctor: Mapped[Doctor] = relationship(  # noqa: F821
        "Doctor", back_populates="availability_slots"
    )
    consultation: Mapped[Consultation | None] = relationship(  # noqa: F821
        "Consultation", back_populates="slot", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<AvailabilitySlot id={self.id} doctor_id={self.doctor_id} "
            f"start={self.start_time} booked={self.is_booked}>"
        )
