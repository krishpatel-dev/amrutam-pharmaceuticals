"""Consultation and ConsultationNote ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.availability import AvailabilitySlot
    from app.models.doctor import Doctor
    from app.models.payment import Payment
    from app.models.prescription import Prescription
    from app.models.user import User


class ConsultationStatus:
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Consultation(Base):
    """
    A booked consultation session between a patient and a doctor.

    The ``idempotency_key`` UNIQUE constraint prevents double-booking
    even if the client retries the same POST /consultations request.
    """

    __tablename__ = "consultations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Participants
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        unique=True,  # One consultation per slot
        nullable=False,
    )

    # State
    status: Mapped[str] = mapped_column(
        Enum(
            "scheduled",
            "in_progress",
            "completed",
            "cancelled",
            "no_show",
            name="consultation_status_enum",
        ),
        default="scheduled",
        nullable=False,
        index=True,
    )

    # Content
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Idempotency — ensures retried booking requests are not duplicated
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    patient: Mapped[User] = relationship(  # noqa: F821
        "User", foreign_keys=[patient_id], back_populates="consultations_as_patient"
    )
    doctor: Mapped[Doctor] = relationship(  # noqa: F821
        "Doctor", foreign_keys=[doctor_id], back_populates="consultations"
    )
    slot: Mapped[AvailabilitySlot] = relationship(  # noqa: F821
        "AvailabilitySlot", back_populates="consultation"
    )
    notes: Mapped[list[ConsultationNote]] = relationship(
        "ConsultationNote",
        back_populates="consultation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    prescription: Mapped[Prescription | None] = relationship(  # noqa: F821
        "Prescription", back_populates="consultation", uselist=False
    )
    payment: Mapped[Payment | None] = relationship(  # noqa: F821
        "Payment", back_populates="consultation", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Consultation id={self.id} status={self.status}>"


class ConsultationNote(Base):
    """Clinical notes added during a consultation (by doctor or admin)."""

    __tablename__ = "consultation_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    consultation: Mapped[Consultation] = relationship("Consultation", back_populates="notes")

    def __repr__(self) -> str:
        return f"<ConsultationNote id={self.id} consultation_id={self.consultation_id}>"
