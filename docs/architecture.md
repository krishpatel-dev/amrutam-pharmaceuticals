# Architecture Notes — Amrutam Pharmaceuticals Backend

## Overview

This is an async REST API built with FastAPI + PostgreSQL, targeting around 100k daily consultations.
Three user roles: patients, doctors, and admins.

```
               Clients (web / mobile)
                        |
               Load Balancer (nginx)
               /                   \
        API Instance 1    ...   API Instance N
        FastAPI+Gunicorn          FastAPI+Gunicorn
               \                   /
                \                 /
            +---+------ shared ----+---+
            |           |              |
      PostgreSQL 16   Redis 7     Celery Workers
      (+ replica)  (cache+broker)  (email, PDF, etc)
```

## Components

### API (FastAPI)

All endpoints are async — using `asyncpg` so no thread pool blocking.
Production server: Gunicorn with uvicorn workers (~2x CPU cores + 1).

Middleware order (outermost first):
1. CORSMiddleware
2. Rate limiter (slowapi + Redis)
3. AuditLogMiddleware — logs all write requests
4. SecurityHeadersMiddleware — sets OWASP-recommended headers
5. RequestIDMiddleware — attaches X-Request-ID for log correlation

### Database (PostgreSQL 16)

- SQLAlchemy 2.0 with async sessions
- Connection pool: 20 connections, 10 overflow, pre-ping enabled
- `audit_logs` table: monthly range partitioned on `created_at`
- `consultations` table: yearly range partitioned
- Read replicas can be plugged into the session factory for GET requests
- Every FK, status field, and timestamp column is indexed

### Cache (Redis 7)

- DB 0: app cache (doctor search results, TTL 5 min, key = SHA256 of query params)
- DB 1: Celery broker
- DB 2: Celery results
- Also used for rate limit counters (atomic INCR)

### Background Workers (Celery)

Tasks: booking confirmation email, 24h reminder, prescription PDF, rating recalc.
All tasks use `acks_late=True` and `prefetch_multiplier=1` for safe retry behaviour.
Retry policy: max 3 retries, exponential backoff (60s → 120s → 240s).

## Booking Flow

```
Patient     →  POST /consultations
API         →  check idempotency key exists in DB (return cached result if yes)
API         →  SELECT availability_slot FOR UPDATE  (pessimistic lock)
API         →  set slot.is_booked = True
API         →  INSERT consultation row
API         →  COMMIT transaction
API         →  invalidate Redis search cache
API         →  enqueue booking confirmation email (Celery)
API         ←  201 Created
```

The `SELECT FOR UPDATE` guarantees only one booking per slot even under concurrent requests.
The `idempotency_key` unique constraint prevents duplicate rows on network retries.

## Data Model (simplified)

```
users (1) ──── (1) user_profiles
  |
  └── (1) ──── (1) doctors
                     |
                     └── (1:N) availability_slots
                                    |
                                    └── (1:1) consultations
                                                  |
                                                  ├── (1:N) consultation_notes
                                                  ├── (1:1) prescriptions
                                                  │            └── (1:N) medications
                                                  └── (1:1) payments

users (1) ──── (1:N) audit_logs
```

Full ER diagram with column types is in `docs/er-diagram.md`.

## Scalability

- **Read heavy load**: Redis caches doctor search results for 5 minutes
- **Double-booking**: Solved with `SELECT FOR UPDATE` at the DB level
- **Idempotent writes**: Unique `idempotency_key` per booking and payment
- **Connection pressure**: Pool + read replicas for GET queries
- **Slow tasks**: Offloaded to Celery (email, PDF generation)
- **Horizontal scale**: API is stateless; Redis holds shared rate limit and session state
- **Audit table growth**: Monthly partitioning keeps query performance stable

## Backup and Recovery

- Daily pg_dump + WAL streaming to object storage
- RPO target: < 1 hour
- RTO target: < 4 hours
- Redis: AOF persistence on
- Failover: promote read replica manually or via PgBouncer

## Why these choices

- **FastAPI over Django/Flask**: Native async, auto-generates OpenAPI docs, fastest Python framework for IO-bound work
- **SQLAlchemy 2.0**: Type-safe ORM with proper async support via asyncpg
- **JWT HS256 + TOTP**: Stateless auth, no server-side session storage needed
- **slowapi + Redis**: Distributed rate limiting works across multiple API instances
- **structlog + OpenTelemetry**: JSON structured logs are machine-parseable; OTel traces work with any CNCF-compatible backend
