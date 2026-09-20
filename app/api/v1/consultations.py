"""Consultations API router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status

from app.core.dependencies import (
    CurrentUserID,
    CurrentUserRole,
    DBSession,
    IdempotencyKey,
    Pagination,
    RequireDoctor,
    RequirePatient,
)
from app.repositories.consultation_repo import ConsultationRepository
from app.schemas.common import PaginationMeta, SuccessResponse
from app.schemas.consultation import (
    BookingRequest,
    CancelConsultationRequest,
    ConsultationNoteCreate,
    ConsultationOut,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/consultations", tags=["Consultations"])


def _get_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Book a consultation (patient only)",
    dependencies=[RequirePatient],
)
async def book_consultation(
    request: Request,
    body: BookingRequest,
    user_id: CurrentUserID,
    db: DBSession,
    idempotency_key: IdempotencyKey = None,
) -> SuccessResponse:
    service = BookingService(db)
    consultation = await service.book_consultation(
        patient_id=uuid.UUID(user_id),
        data=body,
        idempotency_key=idempotency_key,
        ip=_get_ip(request),
    )
    return SuccessResponse(
        message="Consultation booked successfully.",
        data=consultation.model_dump(mode="json"),
    )


@router.get(
    "",
    summary="List my consultations",
)
async def list_consultations(
    user_id: CurrentUserID,
    role: CurrentUserRole,
    db: DBSession,
    pagination: Pagination,
) -> SuccessResponse:
    repo = ConsultationRepository(db)
    uid = uuid.UUID(user_id)

    if role == "patient":
        items = await repo.get_patient_consultations(uid, pagination.offset, pagination.page_size)
        total = await repo.count(patient_id=uid)
    elif role == "doctor":
        from app.repositories.doctor_repo import DoctorRepository
        doctor = await DoctorRepository(db).get_by_user_id(uid)
        if not doctor:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Doctor profile not found.")
        items = await repo.get_doctor_consultations(
            doctor.id, offset=pagination.offset, limit=pagination.page_size
        )
        total = await repo.count(doctor_id=doctor.id)
    else:
        # Admin: get all
        items = await repo.get_all(offset=pagination.offset, limit=pagination.page_size)
        total = await repo.count()

    data = [ConsultationOut.model_validate(c).model_dump(mode="json") for c in items]
    return SuccessResponse(data={
        "items": data,
        "pagination": PaginationMeta.build(
            pagination.page, pagination.page_size, total
        ).model_dump(),
    })


@router.get(
    "/{consultation_id}",
    summary="Get consultation details",
)
async def get_consultation(
    consultation_id: uuid.UUID,
    user_id: CurrentUserID,
    role: CurrentUserRole,
    db: DBSession,
) -> SuccessResponse:
    repo = ConsultationRepository(db)
    consultation = await repo.get_with_details(consultation_id)
    if not consultation:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Consultation not found.")

    uid = uuid.UUID(user_id)
    # Patients can only see their own; doctors can see theirs; admins see all
    if role == "patient" and consultation.patient_id != uid:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()

    return SuccessResponse(
        data=ConsultationOut.model_validate(consultation).model_dump(mode="json")
    )


@router.put(
    "/{consultation_id}/start",
    summary="Start a consultation (doctor only)",
    dependencies=[RequireDoctor],
)
async def start_consultation(
    consultation_id: uuid.UUID,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    from app.repositories.doctor_repo import DoctorRepository
    doctor = await DoctorRepository(db).get_by_user_id(uuid.UUID(user_id))
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Doctor profile not found.")

    service = BookingService(db)
    result = await service.start_consultation(consultation_id, doctor.id)
    return SuccessResponse(message="Consultation started.", data=result.model_dump(mode="json"))


@router.put(
    "/{consultation_id}/end",
    summary="End a consultation (doctor only)",
    dependencies=[RequireDoctor],
)
async def end_consultation(
    consultation_id: uuid.UUID,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    from app.repositories.doctor_repo import DoctorRepository
    doctor = await DoctorRepository(db).get_by_user_id(uuid.UUID(user_id))
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Doctor profile not found.")

    service = BookingService(db)
    result = await service.end_consultation(consultation_id, doctor.id)
    return SuccessResponse(message="Consultation completed.", data=result.model_dump(mode="json"))


@router.post(
    "/{consultation_id}/notes",
    status_code=status.HTTP_201_CREATED,
    summary="Add a clinical note (doctor only)",
    dependencies=[RequireDoctor],
)
async def add_note(
    consultation_id: uuid.UUID,
    body: ConsultationNoteCreate,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = BookingService(db)
    result = await service.add_note(consultation_id, uuid.UUID(user_id), body)
    return SuccessResponse(message="Note added.", data=result.model_dump(mode="json"))


@router.put(
    "/{consultation_id}/cancel",
    summary="Cancel a consultation",
)
async def cancel_consultation(
    consultation_id: uuid.UUID,
    body: CancelConsultationRequest,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = BookingService(db)
    result = await service.cancel_consultation(
        consultation_id, uuid.UUID(user_id), body.reason
    )
    return SuccessResponse(message="Consultation cancelled.", data=result.model_dump(mode="json"))
