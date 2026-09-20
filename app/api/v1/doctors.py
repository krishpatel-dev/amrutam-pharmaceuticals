"""Doctors API router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUserID, DBSession, RequireAdmin, RequireDoctor
from app.schemas.common import SuccessResponse
from app.schemas.doctor import DoctorCreate, DoctorUpdateRequest, DoctorVerifyRequest
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post(
    "/me",
    status_code=status.HTTP_201_CREATED,
    summary="Create doctor profile (doctor role required)",
    dependencies=[RequireDoctor],
)
async def create_doctor_profile(
    user_id: CurrentUserID,
    body: DoctorCreate,
    db: DBSession,
) -> SuccessResponse:
    service = DoctorService(db)
    doctor = await service.create_doctor_profile(uuid.UUID(user_id), body)
    return SuccessResponse(
        message="Doctor profile created and pending verification.",
        data=doctor.model_dump(mode="json"),
    )


@router.get(
    "/me",
    summary="Get own doctor profile",
    dependencies=[RequireDoctor],
)
async def get_my_profile(
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = DoctorService(db)
    doctor = await service.get_my_profile(uuid.UUID(user_id))
    return SuccessResponse(data=doctor.model_dump(mode="json"))


@router.put(
    "/me",
    summary="Update own doctor profile",
    dependencies=[RequireDoctor],
)
async def update_doctor_profile(
    user_id: CurrentUserID,
    body: DoctorUpdateRequest,
    db: DBSession,
) -> SuccessResponse:
    service = DoctorService(db)
    doctor = await service.update_profile(uuid.UUID(user_id), body)
    return SuccessResponse(message="Profile updated.", data=doctor.model_dump(mode="json"))


@router.get(
    "/{doctor_id}",
    summary="Get public doctor profile",
)
async def get_doctor(
    doctor_id: uuid.UUID,
    db: DBSession,
) -> SuccessResponse:
    service = DoctorService(db)
    doctor = await service.get_doctor(doctor_id)
    return SuccessResponse(data=doctor.model_dump(mode="json"))


@router.put(
    "/{doctor_id}/verify",
    summary="Verify or reject a doctor (admin only)",
    dependencies=[RequireAdmin],
)
async def verify_doctor(
    doctor_id: uuid.UUID,
    body: DoctorVerifyRequest,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = DoctorService(db)
    doctor = await service.verify_doctor(doctor_id, body.is_verified, uuid.UUID(user_id))
    action = "verified" if body.is_verified else "rejected"
    return SuccessResponse(
        message=f"Doctor has been {action}.",
        data=doctor.model_dump(mode="json"),
    )
