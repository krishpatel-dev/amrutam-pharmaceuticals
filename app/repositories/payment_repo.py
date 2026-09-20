"""Payment repository."""

from __future__ import annotations

from sqlalchemy import select

from app.models.payment import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_by_gateway_ref(self, gateway_ref: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.gateway_ref == gateway_ref)
        )
        return result.scalar_one_or_none()

    async def get_by_consultation_id(self, consultation_id) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.consultation_id == consultation_id)
        )
        return result.scalar_one_or_none()
