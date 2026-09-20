"""Search service — doctor search with Redis caching."""

from __future__ import annotations

import hashlib

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.doctor import DoctorPublicOut
from app.schemas.search import DoctorSearchParams
from app.schemas.user import ProfileOut

logger = structlog.get_logger(__name__)


class SearchService:
    def __init__(self, db: AsyncSession, redis=None) -> None:
        self._doctor_repo = DoctorRepository(db)
        self._redis = redis

    async def search_doctors(
        self, params: DoctorSearchParams
    ) -> PaginatedResponse[DoctorPublicOut]:
        """
        Search doctors with optional Redis cache.

        Cache key: SHA256 hash of the serialized search parameters.
        TTL: ``settings.CACHE_TTL_SECONDS`` (default 5 min).
        """
        cache_key = self._build_cache_key(params)

        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                logger.debug("search_cache_hit", key=cache_key)
                return PaginatedResponse[DoctorPublicOut].model_validate_json(cached)

        doctors, total = await self._doctor_repo.search(params)

        results: list[DoctorPublicOut] = []
        for doc in doctors:
            profile_out = None
            if doc.user and doc.user.profile:
                p = doc.user.profile
                profile_out = ProfileOut(
                    first_name=p.first_name,
                    last_name=p.last_name,
                    full_name=p.full_name,
                )
            results.append(
                DoctorPublicOut(
                    id=doc.id,
                    specialty=doc.specialty,
                    bio=doc.bio,
                    years_experience=doc.years_experience,
                    consultation_fee=doc.consultation_fee,
                    languages=doc.languages,
                    rating=doc.rating,
                    total_consultations=doc.total_consultations,
                    total_reviews=doc.total_reviews,
                    profile=profile_out,
                )
            )

        response = PaginatedResponse[DoctorPublicOut](
            data=results,
            pagination=PaginationMeta.build(params.page, params.page_size, total),
        )

        if self._redis:
            await self._redis.setex(
                cache_key,
                settings.CACHE_TTL_SECONDS,
                response.model_dump_json(),
            )
            logger.debug("search_cache_set", key=cache_key)

        return response

    @staticmethod
    def _build_cache_key(params: DoctorSearchParams) -> str:
        raw = params.model_dump_json(exclude_none=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"search:doctors:{digest}"
