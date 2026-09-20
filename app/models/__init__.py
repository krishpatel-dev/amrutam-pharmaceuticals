"""Models package — imports all ORM models for Alembic auto-discovery."""

from app.models.audit import AuditLog
from app.models.availability import AvailabilitySlot
from app.models.consultation import Consultation, ConsultationNote
from app.models.doctor import Doctor
from app.models.payment import Payment
from app.models.prescription import Medication, Prescription
from app.models.user import User, UserProfile

__all__ = [
    "User",
    "UserProfile",
    "Doctor",
    "AvailabilitySlot",
    "Consultation",
    "ConsultationNote",
    "Prescription",
    "Medication",
    "Payment",
    "AuditLog",
]
