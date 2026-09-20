"""Users API router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.dependencies import CurrentUserID, DBSession
from app.repositories.user_repo import UserProfileRepository, UserRepository
from app.schemas.common import SuccessResponse
from app.schemas.user import ProfileUpdateRequest, UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Get current user profile",
)
async def get_me(
    user_id: CurrentUserID,
    db: DBSession,
) -> SuccessResponse:
    repo = UserRepository(db)
    user = await repo.get_with_profile(uuid.UUID(user_id))
    if not user:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("User not found.")
    return SuccessResponse(data=UserOut.model_validate(user).model_dump(mode="json"))


@router.put(
    "/me",
    summary="Update current user profile",
)
async def update_me(
    user_id: CurrentUserID,
    body: ProfileUpdateRequest,
    db: DBSession,
) -> SuccessResponse:
    profile_repo = UserProfileRepository(db)
    profile = await profile_repo.get_by_user_id(uuid.UUID(user_id))
    if not profile:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Profile not found.")

    updates = body.model_dump(exclude_none=True)
    updated = await profile_repo.update(profile, **updates)
    return SuccessResponse(
        message="Profile updated successfully.",
        data={"id": str(updated.id), **updates},
    )
