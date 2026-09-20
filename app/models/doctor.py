"""Doctor ORM model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.availability import AvailabilitySlot
    from app.models.consultation import Consultation
    from app.models.user import User


class Doctor(Base):
    """Doctor professional profile — linked 1:1 with User."""

    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Professional details
    specialty: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    license_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consultation_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    languages: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated

    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Metrics (denormalized for read performance)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_consultations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(  # noqa: F821
        "User", back_populates="doctor_profile", foreign_keys=[user_id]
    )
    availability_slots: Mapped[list[AvailabilitySlot]] = relationship(  # noqa: F821
        "AvailabilitySlot", back_populates="doctor", cascade="all, delete-orphan"
    )
    consultations: Mapped[list[Consultation]] = relationship(  # noqa: F821
        "Consultation", foreign_keys="Consultation.doctor_id", back_populates="doctor"
    )

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} specialty={self.specialty} verified={self.is_verified}>"
