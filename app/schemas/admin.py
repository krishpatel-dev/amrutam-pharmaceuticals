"""Admin analytics schemas."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import BaseSchema


class OverviewStats(BaseSchema):
    total_users: int
    total_patients: int
    total_doctors: int
    verified_doctors: int
    total_consultations: int
    active_consultations: int
    completed_consultations: int
    total_revenue: float
    revenue_currency: str = "INR"


class ConsultationTrend(BaseSchema):
    date: str  # "YYYY-MM-DD"
    count: int
    completed: int
    cancelled: int


class RevenueSummary(BaseSchema):
    period: str  # "daily" | "monthly"
    date: str
    revenue: float
    transaction_count: int


class AuditLogOut(BaseSchema):
    id: str
    user_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    outcome: str
    created_at: datetime
