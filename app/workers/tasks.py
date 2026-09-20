"""Celery background tasks."""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="tasks.send_booking_confirmation",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_booking_confirmation(
    self, patient_email: str, consultation_id: str, slot_time: str
) -> None:
    """Send booking confirmation email to the patient."""
    try:
        # In production: integrate with SendGrid/SES
        logger.info(
            "sending_booking_confirmation",
            email=patient_email,
            consultation_id=consultation_id,
        )
        # email_client.send(to=patient_email, template="booking_confirmation", ...)
    except Exception as exc:
        logger.error("booking_confirmation_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.send_consultation_reminder",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def send_consultation_reminder(
    self, patient_email: str, doctor_email: str, consultation_id: str
) -> None:
    """Send 24-hour reminder to both patient and doctor."""
    try:
        logger.info(
            "sending_reminder",
            consultation_id=consultation_id,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.generate_prescription_pdf",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def generate_prescription_pdf(self, prescription_id: str) -> str:
    """Generate a PDF for a prescription and return the storage URL."""
    try:
        logger.info("generating_prescription_pdf", prescription_id=prescription_id)
        # In production: use reportlab or weasyprint to generate PDF
        # Upload to S3/GCS and return URL
        return f"https://storage.amrutam.com/prescriptions/{prescription_id}.pdf"
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.update_doctor_rating",
    bind=True,
    max_retries=3,
)
def update_doctor_rating(self, doctor_id: str) -> None:
    """Recalculate and update a doctor's average rating after a new review."""
    try:
        logger.info("updating_doctor_rating", doctor_id=doctor_id)
        # Aggregate rating from reviews table and update Doctor.rating
    except Exception as exc:
        raise self.retry(exc=exc)
