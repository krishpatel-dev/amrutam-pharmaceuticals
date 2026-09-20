"""Admin API router."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUserID, DBSession, Pagination, RequireAdmin
from app.repositories.user_repo import UserRepository
from app.schemas.common import SuccessResponse
from app.schemas.user import AdminUserOut, UserStatusUpdateRequest
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[RequireAdmin])


@router.get(
    "/analytics/overview",
    summary="Platform overview statistics",
)
async def get_overview(db: DBSession) -> SuccessResponse:
    service = AdminService(db)
    stats = await service.get_overview()
    return SuccessResponse(data=stats.model_dump())


@router.get(
    "/analytics/consultations",
    summary="Consultation trends (last N days)",
)
async def get_consultation_trends(
    db: DBSession,
    days: int = Query(default=30, ge=1, le=365),
) -> SuccessResponse:
    service = AdminService(db)
    trends = await service.get_consultation_trends(days)
    return SuccessResponse(data=[t.model_dump() for t in trends])


@router.get(
    "/analytics/revenue",
    summary="Revenue summary",
)
async def get_revenue(
    db: DBSession,
    period: str = Query(default="daily", pattern="^(daily|monthly)$"),
) -> SuccessResponse:
    service = AdminService(db)
    summary = await service.get_revenue_summary(period)
    return SuccessResponse(data=[s.model_dump() for s in summary])


@router.get(
    "/users",
    summary="List all users",
)
async def list_users(
    db: DBSession,
    pagination: Pagination,
    role: str | None = Query(default=None, pattern="^(patient|doctor|admin)$"),
) -> SuccessResponse:

    repo = UserRepository(db)
    filters = {}
    if role:
        filters["role"] = role
    users = await repo.get_all(
        offset=pagination.offset, limit=pagination.page_size, **filters
    )
    total = await repo.count(**filters)
    return SuccessResponse(data={
        "items": [AdminUserOut.model_validate(u).model_dump(mode="json") for u in users],
        "total": total,
    })


@router.put(
    "/users/{user_id}/status",
    summary="Activate or deactivate a user",
)
async def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdateRequest,
    admin_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    from app.repositories.audit_repo import AuditRepository

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("User not found.")

    await repo.update(user, is_active=body.is_active)  # noqa: F841
    action = "activated" if body.is_active else "deactivated"

    await AuditRepository(db).log(
        action=f"user_{action}",
        user_id=uuid.UUID(admin_id),
        resource_type="user",
        resource_id=str(user_id),
    )

    return SuccessResponse(message=f"User has been {action}.")


@router.get(
    "/audit-logs",
    summary="Get audit logs",
)
async def get_audit_logs(
    db: DBSession,
    pagination: Pagination,
    action: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
) -> SuccessResponse:
    service = AdminService(db)
    logs = await service.get_audit_logs(
        offset=pagination.offset,
        limit=pagination.page_size,
        action=action,
        from_date=from_date,
        to_date=to_date,
    )
    return SuccessResponse(data=[entry.model_dump(mode="json") for entry in logs])
