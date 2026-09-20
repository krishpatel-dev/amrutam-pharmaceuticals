# Threat Model — Amrutam Pharmaceuticals Platform

Comprehensive threat modeling analysis based on the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege), covering data classification, trust boundaries, attack surface, and security controls.

---

## 1. System Overview & Trust Boundaries

```
[ Public Zone: Patients / Doctors / Attackers ]
                      │  (TLS 1.3 / HTTPS)
                      ▼
┌────────────────────────────────────────────────────────┐
│ DMZ / Boundary: Ingress & Rate Limiter                 │
│  - slowapi (Per-IP / Per-User Token Bucket)            │
│  - SecurityHeadersMiddleware (HSTS, CSP, X-Frame)      │
│  - RequestIDMiddleware (Traceability)                  │
└────────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│ Application Zone: FastAPI Core Services                │
│  - JWT Bearer Authentication + TOTP MFA Verification   │
│  - RBAC Engine (Patient, Doctor, Admin)                │
│  - Pydantic v2 Input Sanitization & Validation         │
│  - Idempotency Gatekeeper (X-Idempotency-Key)          │
│  - Audit Logging Middleware                            │
└────────────────────────────────────────────────────────┘
        │                            │
        ▼                            ▼
┌───────────────────────┐    ┌───────────────────────────┐
│ Data Zone: PostgreSQL │    │ Cache & Broker: Redis 7   │
│  - PHI Isolation      │    │  - DB 0: Query Cache      │
│  - Row-Level Locking  │    │  - DB 1: Celery Broker    │
│  - AES-256 at Rest    │    │  - DB 2: Celery Results   │
└───────────────────────┘    └───────────────────────────┘
```

### Trust Zones
1. **Untrusted Zone**: Web browsers, mobile clients, external payment webhook callers.
2. **DMZ / Gateway**: Load balancer and ingress proxy terminating TLS and enforcing IP-level rate limits.
3. **Internal Application Zone**: FastAPI application runtime, Celery background task workers.
4. **Secure Data Zone**: Isolated private VPC network containing PostgreSQL 16 database and Redis 7 cache.

---

## 2. Asset & Data Classification

| Classification | Assets | Security Objectives | Controls |
|---|---|---|---|
| **PHI (Protected Health Information)** | Consultation notes, Prescriptions, Medical history, Diagnosis, Chief complaints | Confidentiality & Integrity (HIPAA / DISHA) | Storage restricted to dedicated tables, never logged in application logs or audit logs, accessible only by assigned patient & doctor. |
| **PII (Personally Identifiable Information)** | User profile (name, phone, address, DOB, email) | Privacy & Compliance (DPDP Act) | Access restricted by user ownership and admin role. |
| **Financial Data** | Payment amounts, gateway transaction references, webhook events | Financial Integrity & Non-Repudiation | HMAC-SHA256 signature verification, idempotency keys, no raw credit card details stored. |
| **Authentication Secrets** | Password hashes (bcrypt 12 rounds), MFA secrets, JWT private keys | Confidentiality & Authentication Assurance | Salted bcrypt, environment-injected secret keys, minimum 32-character high-entropy secrets. |

---

## 3. STRIDE Threat Analysis

### 3.1. Spoofing Identity
- **Threat**: Attacker impersonates a doctor to view patient medical records or issue fraudulent prescriptions.
- **Threat**: Attacker brute-forces patient accounts or sends forged authentication requests.
- **Mitigations**:
  - Bcrypt (12 rounds) salted hashing for password storage.
  - Short-lived asymmetric/symmetric JWT access tokens (15 minutes expiry) with distinct JTI IDs.
  - Mandatory TOTP multi-factor authentication (RFC 6238 via `pyotp`) for privileged roles and critical transactions.
  - Strict rate limiting on `/api/v1/auth/login` (10 requests/minute per IP).
  - Constant-time password verification preventing side-channel timing attacks.

### 3.2. Tampering with Data
- **Threat**: Attacker tampers with consultation pricing or booking parameters.
- **Threat**: Attacker tampers with payment webhook payloads to mark unpaid consultations as paid.
- **Threat**: SQL injection into doctor search or consultation endpoints.
- **Mitigations**:
  - Full ORM abstraction using SQLAlchemy 2.0 with parameterized queries — zero raw SQL execution.
  - Strict Pydantic v2 schemas validating every input field type, regex patterns, and range boundaries before execution.
  - Payment gateway webhooks require HMAC-SHA256 signature validation with `hmac.compare_digest` using shared webhook secrets.
  - Pricing is calculated server-side based on the verified doctor profile in PostgreSQL, never accepted from client payload.

### 3.3. Repudiation
- **Threat**: Doctor denies issuing a prescription or patient denies cancelling an appointment.
- **Threat**: Malicious admin modifies user records without accountability.
- **Mitigations**:
  - Comprehensive, immutable `audit_logs` table partitioned monthly.
  - Every write and mutation request records: `user_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `timestamp`, and `outcome`.
  - Application logs emitted as structured JSON via `structlog` containing correlation `request_id` values.
  - Prescriptions link explicitly to `issued_by` user UUID and include immutable creation timestamps.

### 3.4. Information Disclosure
- **Threat**: Leaking PHI or medical records across patient boundaries (Broken Object-Level Authorization / BOLA / IDOR).
- **Threat**: Internal stack traces or database schema leaked in 500 error responses.
- **Threat**: Sensitive tokens or PHI dumped into application logs.
- **Mitigations**:
  - Fine-grained object ownership checks in `consultation_service.py` and `prescription_service.py`: patients can only retrieve consultations where `patient_id == current_user.id`; doctors can only retrieve consultations where `doctor_id == current_user.doctor_profile.id`.
  - Global FastAPI exception handlers intercept all unhandled exceptions, log the stack trace internally with correlation ID, and return clean generic error responses to clients.
  - Audit logging middleware excludes password fields, token headers, and PHI payloads from log records.
  - Security headers added: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy`.

### 3.5. Denial of Service (DoS)
- **Threat**: Slot hoarding or race-condition double booking of doctors' consultation slots.
- **Threat**: Resource exhaustion via endpoint flooding or large payload attacks.
- **Mitigations**:
  - Pessimistic locking (`SELECT FOR UPDATE`) on `availability_slots` inside database transactions guarantees atomic, race-free slot reservations.
  - Distributed token-bucket rate limiting via `slowapi` backed by Redis counters across all API instances.
  - Mandatory `X-Idempotency-Key` headers on write endpoints preventing duplicate execution and redundant load on network retries.
  - Bounded pagination limits (`page_size` capped at 100) preventing memory exhaustion during doctor searches.

### 3.6. Elevation of Privilege
- **Threat**: A patient alters their JWT token or user profile to gain `doctor` or `admin` permissions.
- **Mitigations**:
  - Role (`patient`, `doctor`, `admin`) is cryptographically signed inside the JWT payload using `HS256` with a 32+ character high-entropy secret.
  - Role verification enforced via FastAPI dependency injection (`require_roles("admin")`, `require_roles("doctor")`).
  - Self-service role promotion is prohibited; doctor verification requires administrative action (`is_verified` flag managed by admin).

---

## 4. Key Management & Secrets Lifecycle

1. **Storage**: All production secrets (`APP_SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, `PAYMENT_WEBHOOK_SECRET`) injected via environment variables; never checked into version control.
2. **Rotation Policy**:
   - Access tokens: 15-minute auto-expiry requires zero key rotation for revocation.
   - JWT Secret: Rotated quarterly using key IDs (`kid`) with dual-key validation during transition periods.
   - Database Passwords: Rotated semi-annually with zero-downtime connection pool draining.
3. **CI/CD Hygiene**: Automated secret scanning and dependency audits (`bandit`, `safety`) executed on every commit.
