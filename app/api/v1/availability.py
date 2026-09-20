"""Availability slots API router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUserID, DBSession, RequireDoctor
from app.repositories.availability_repo import AvailabilityRepository
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.availability import SlotBulkCreate, SlotOut
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/availability", tags=["Availability"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create availability slots (doctor only)",
    dependencies=[RequireDoctor],
)
async def create_slots(
    user_id: CurrentUserID,
    body: SlotBulkCreate,
    db: DBSession,
) -> SuccessResponse:
    doctor_repo = DoctorRepository(db)
    doctor = await doctor_repo.get_by_user_id(uuid.UUID(user_id))
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Doctor profile not found.")

    slot_repo = AvailabilityRepository(db)
    created = []
    for slot_data in body.slots:
        slot = await slot_repo.create(
            doctor_id=doctor.id,
            start_time=slot_data.start_time,
            end_time=slot_data.end_time,
            duration_minutes=slot_data.duration_minutes,
            recurrence_rule=slot_data.recurrence_rule,
        )
        created.append(SlotOut.model_validate(slot).model_dump(mode="json"))

    return SuccessResponse(
        message=f"{len(created)} slot(s) created successfully.",
        data=created,
    )


@router.get(
    "/me",
    summary="Get my availability slots (doctor only)",
    dependencies=[RequireDoctor],
)
async def get_my_slots(
    user_id: CurrentUserID,
    db: DBSession,
    only_available: bool = Query(default=False),
) -> SuccessResponse:
    doctor_repo = DoctorRepository(db)
    doctor = await doctor_repo.get_by_user_id(uuid.UUID(user_id))
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Doctor profile not found.")

    slot_repo = AvailabilityRepository(db)
    slots = await slot_repo.get_doctor_slots(
        doctor.id,
        from_time=datetime.now(UTC),
        only_available=only_available,
    )
    return SuccessResponse(data=[SlotOut.model_validate(s).model_dump(mode="json") for s in slots])


@router.get(
    "/{doctor_id}",
    summary="Get a doctor's available slots (any authenticated user)",
)
async def get_doctor_slots(
    doctor_id: uuid.UUID,
    db: DBSession,
    _: CurrentUserID,  # Require authentication
) -> SuccessResponse:
    slot_repo = AvailabilityRepository(db)
    slots = await slot_repo.get_doctor_slots(
        doctor_id,
        from_time=datetime.now(UTC),
        only_available=True,
    )
    return SuccessResponse(data=[SlotOut.model_validate(s).model_dump(mode="json") for s in slots])


@router.delete(
    "/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a slot (doctor only)",
    dependencies=[RequireDoctor],
)
async def delete_slot(
    slot_id: uuid.UUID,
    user_id: CurrentUserID,
    db: DBSession,
) -> None:
    doctor_repo = DoctorRepository(db)
    doctor = await doctor_repo.get_by_user_id(uuid.UUID(user_id))
    if not doctor:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Doctor profile not found.")

    slot_repo = AvailabilityRepository(db)
    slot = await slot_repo.get_by_id(slot_id)
    if not slot:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Slot not found.")

    if slot.doctor_id != doctor.id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("You can only delete your own slots.")

    if slot.is_booked:
        from app.core.exceptions import ConflictError
        raise ConflictError("Cannot delete a booked slot.")

    await slot_repo.delete(slot)
