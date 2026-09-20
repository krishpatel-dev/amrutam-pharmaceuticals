"""Admin analytics service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.repositories.audit_repo import AuditRepository
from app.schemas.admin import AuditLogOut, ConsultationTrend, OverviewStats, RevenueSummary


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit_repo = AuditRepository(db)

    async def get_overview(self) -> OverviewStats:
        """Pull overview stats for the admin dashboard."""

        total_users = await self._scalar(select(func.count()).select_from(User))
        total_patients = await self._scalar(
            select(func.count()).select_from(User).where(User.role == "patient")
        )
        total_doctors = await self._scalar(
            select(func.count()).select_from(User).where(User.role == "doctor")
        )
        verified_doctors = await self._scalar(
            select(func.count()).select_from(Doctor).where(Doctor.is_verified == True)  # noqa: E712
        )
        total_consultations = await self._scalar(
            select(func.count()).select_from(Consultation)
        )
        active_consultations = await self._scalar(
            select(func.count())
            .select_from(Consultation)
            .where(Consultation.status == "in_progress")
        )
        completed_consultations = await self._scalar(
            select(func.count())
            .select_from(Consultation)
            .where(Consultation.status == "completed")
        )
        total_revenue = await self._scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .select_from(Payment)
            .where(Payment.status == PaymentStatus.COMPLETED)
        )

        return OverviewStats(
            total_users=total_users,
            total_patients=total_patients,
            total_doctors=total_doctors,
            verified_doctors=verified_doctors,
            total_consultations=total_consultations,
            active_consultations=active_consultations,
            completed_consultations=completed_consultations,
            total_revenue=float(total_revenue or 0),
        )

    async def get_consultation_trends(self, days: int = 30) -> list[ConsultationTrend]:
        """Daily consultation counts for the last N days."""
        result = await self._db.execute(
            select(
                func.date(Consultation.created_at).label("date"),
                func.count().label("count"),
                func.sum(
                    case((Consultation.status == "completed", 1), else_=0)
                ).label("completed"),
                func.sum(
                    case((Consultation.status == "cancelled", 1), else_=0)
                ).label("cancelled"),
            )
            .select_from(Consultation)
            .group_by(func.date(Consultation.created_at))
            .order_by(func.date(Consultation.created_at).desc())
            .limit(days)
        )
        rows = result.fetchall()
        return [
            ConsultationTrend(
                date=str(row.date),
                count=row.count,
                completed=int(row.completed or 0),
                cancelled=int(row.cancelled or 0),
            )
            for row in rows
        ]

    async def get_revenue_summary(self, period: str = "daily") -> list[RevenueSummary]:
        """Revenue aggregated by day or month."""
        if period == "monthly":
            date_trunc = func.date_trunc("month", Payment.created_at)
        else:
            date_trunc = func.date(Payment.created_at)

        result = await self._db.execute(
            select(
                date_trunc.label("date"),
                func.sum(Payment.amount).label("revenue"),
                func.count().label("transaction_count"),
            )
            .select_from(Payment)
            .where(Payment.status == PaymentStatus.COMPLETED)
            .group_by(date_trunc)
            .order_by(date_trunc.desc())
            .limit(30)
        )
        rows = result.fetchall()
        return [
            RevenueSummary(
                period=period,
                date=str(row.date),
                revenue=float(row.revenue or 0),
                transaction_count=row.transaction_count,
            )
            for row in rows
        ]

    async def get_audit_logs(
        self,
        offset: int = 0,
        limit: int = 50,
        action: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[AuditLogOut]:
        logs = await self._audit_repo.get_all_paginated(
            offset=offset, limit=limit, action=action, from_date=from_date, to_date=to_date
        )
        return [
            AuditLogOut(
                id=str(log.id),
                user_id=str(log.user_id) if log.user_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                ip_address=log.ip_address,
                outcome=log.outcome,
                created_at=log.created_at,
            )
            for log in logs
        ]

    async def _scalar(self, stmt) -> int:
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() or 0
