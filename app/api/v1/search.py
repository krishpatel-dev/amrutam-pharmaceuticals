"""Search API router."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserID, DBSession
from app.schemas.common import SuccessResponse
from app.schemas.search import DoctorSearchParams
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "/doctors",
    summary="Search for doctors with filters and pagination",
)
async def search_doctors(
    _: CurrentUserID,
    db: DBSession,
    q: str | None = Query(default=None, max_length=100, description="Name or keyword"),
    specialty: str | None = Query(default=None, max_length=150),
    min_fee: Decimal | None = Query(default=None, ge=0),
    max_fee: Decimal | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0.0, le=5.0),
    min_experience: int | None = Query(default=None, ge=0),
    available_from: datetime | None = Query(default=None),
    available_to: datetime | None = Query(default=None),
    language: str | None = Query(default=None, max_length=50),
    sort_by: str = Query(
        default="rating",
        pattern="^(rating|fee_asc|fee_desc|experience|consultations)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SuccessResponse:
    params = DoctorSearchParams(
        q=q,
        specialty=specialty,
        min_fee=min_fee,
        max_fee=max_fee,
        min_rating=min_rating,
        min_experience=min_experience,
        available_from=available_from,
        available_to=available_to,
        language=language,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    service = SearchService(db)
    result = await service.search_doctors(params)
    return SuccessResponse(data=result.model_dump(mode="json"))
