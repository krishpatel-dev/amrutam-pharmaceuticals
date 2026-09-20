"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    availability,
    consultations,
    doctors,
    payments,
    prescriptions,
    search,
    users,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(doctors.router)
router.include_router(availability.router)
router.include_router(consultations.router)
router.include_router(prescriptions.router)
router.include_router(payments.router)
router.include_router(search.router)
router.include_router(admin.router)
