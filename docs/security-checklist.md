# Security Notes

Quick reference for the security decisions made in this project.

## Auth

- Passwords hashed with bcrypt (12 rounds). Using the `bcrypt` package directly since passlib
  has compatibility issues with bcrypt >= 4.x.
- JWT access tokens expire in 15 minutes. Refresh tokens last 7 days.
- Each token has a `jti` (JWT ID) field — can be used for a revocation blocklist later.
- MFA uses TOTP (RFC 6238) via `pyotp`. Secret stored per-user, QR code returned on setup.
- Auth endpoints are rate-limited to 10 req/min per IP (prevents brute force).

## Authorization

Role-based access via `require_roles()` FastAPI dependency. Roles are: `patient`, `doctor`, `admin`.
Role is embedded in the JWT at login and cannot be changed without re-authenticating.

Resource-level checks are done in the service layer — e.g., a patient can only view their own
consultations, a doctor can only update consultations they're assigned to.

## Input validation

All request bodies go through Pydantic v2 schemas before touching the service layer.
SQLAlchemy ORM is used for all DB writes — no raw SQL, so no injection vectors there.
Query params are validated and bounded (max page_size = 100, etc).

## Payment webhook security

Webhook payloads from the payment gateway are verified with HMAC-SHA256 before processing.
Uses `hmac.compare_digest` for the comparison (constant-time, prevents timing attacks).
Webhook handler is idempotent — replaying the same event is safe.

## HTTP headers

SecurityHeadersMiddleware adds:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (HSTS, 1 year)
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

## PHI handling

PHI (medical notes, prescriptions, diagnoses) lives only in `consultations`,
`consultation_notes`, and `prescriptions` tables.

Audit log entries record *what happened* (action, IP, timestamp, resource ID)
but never copy PHI into the log fields. Stack traces are never sent to the client —
all exceptions are caught and converted to generic error responses.

## Idempotency

All write endpoints that could cause money or booking side-effects (`POST /consultations`,
`POST /payments/webhook`) require an `X-Idempotency-Key` header. The key is stored with
the result; duplicate requests return the stored result without re-executing.

## OWASP coverage

| Risk | What we do |
|------|-----------|
| Broken Access Control | require_roles() on every endpoint + ownership checks |
| Cryptographic Failures | bcrypt for passwords, JWT HS256, TLS + HSTS in prod |
| Injection | Pydantic validation + ORM only (no raw SQL) |
| Insecure Design | PHI isolated, idempotency keys, audit logging |
| Security Misconfiguration | env-based config, no hardcoded secrets, docs off in prod |
| Vulnerable Components | `safety` and `bandit` in CI |
| Identity Failures | short-lived JWTs, refresh rotation, TOTP MFA |
| Software Integrity | HMAC-verified webhooks, pinned Docker base images |
| Logging failures | structlog JSON logs, all mutations audited, Prometheus alerts |
| SSRF | no user-controlled URLs are fetched server-side |

## Dependency scanning

```bash
safety check --full-report
bandit -r app/ -c pyproject.toml
```

Both run in CI on every push to main.
