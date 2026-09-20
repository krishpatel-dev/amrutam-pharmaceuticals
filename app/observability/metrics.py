"""Prometheus metrics definitions."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

active_consultations = Gauge(
    "active_consultations_total",
    "Number of currently in-progress consultations",
)

consultations_total = Counter(
    "consultations_total",
    "Total consultations by status",
    ["status"],  # scheduled, completed, cancelled
)

bookings_total = Counter(
    "bookings_total",
    "Total booking attempts",
    ["outcome"],  # success, slot_unavailable, error
)

payments_total = Counter(
    "payments_total",
    "Total payment events by status",
    ["status"],  # initiated, completed, failed
)

mfa_events_total = Counter(
    "mfa_events_total",
    "MFA login events",
    ["outcome"],  # success, failure
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)
