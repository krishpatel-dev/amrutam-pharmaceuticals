"""Prescription and Medication ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Prescription(Base):
    """Prescription issued by a doctor at the end of a consultation."""

    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    issued_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    consultation: Mapped[Consultation] = relationship(  # noqa: F821
        "Consultation", back_populates="prescription"
    )
    medications: Mapped[list[Medication]] = relationship(
        "Medication", back_populates="prescription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Prescription id={self.id} consultation_id={self.consultation_id}>"


class Medication(Base):
    """Individual medication line item within a prescription."""

    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)         # e.g. "500mg"
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)      # e.g. "twice daily"
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True) # e.g. 7
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)     # e.g. "oral"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription: Mapped[Prescription] = relationship("Prescription", back_populates="medications")

    def __repr__(self) -> str:
        return f"<Medication id={self.id} name={self.name} dosage={self.dosage}>"
