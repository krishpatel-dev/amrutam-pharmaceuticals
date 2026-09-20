"""User repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User, UserProfile
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def get_with_profile(self, user_id) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.profile), selectinload(User.doctor_profile))
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(
            select(User.id).where(User.email == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def create_with_profile(
        self,
        email: str,
        hashed_password: str,
        role: str,
        first_name: str,
        last_name: str,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()

        profile = UserProfile(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(user)
        return user


class UserProfileRepository(BaseRepository[UserProfile]):
    model = UserProfile

    async def get_by_user_id(self, user_id) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
