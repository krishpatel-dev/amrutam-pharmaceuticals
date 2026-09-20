"""Prescriptions API router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUserID, DBSession, RequireDoctor
from app.schemas.common import SuccessResponse
from app.schemas.prescription import PrescriptionCreate
from app.services.prescription_service import PrescriptionService

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Issue a prescription (doctor only)",
    dependencies=[RequireDoctor],
)
async def issue_prescription(
    body: PrescriptionCreate,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = PrescriptionService(db)
    prescription = await service.issue_prescription(uuid.UUID(user_id), body)
    return SuccessResponse(
        message="Prescription issued successfully.",
        data=prescription.model_dump(mode="json"),
    )


@router.get(
    "/{prescription_id}",
    summary="Get a prescription",
)
async def get_prescription(
    prescription_id: uuid.UUID,
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    service = PrescriptionService(db)
    prescription = await service.get_prescription(prescription_id, uuid.UUID(user_id))
    return SuccessResponse(data=prescription.model_dump(mode="json"))
