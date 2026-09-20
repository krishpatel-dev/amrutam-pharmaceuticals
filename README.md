# Amrutam Pharmaceuticals Backend

Backend API for Amrutam's telemedicine platform. Built with FastAPI + PostgreSQL, designed to handle high-volume consultation booking.

## Tech Stack

- **Framework**: FastAPI (async)
- **Database**: PostgreSQL 16 with SQLAlchemy 2.0 (asyncpg)
- **Cache / Queue broker**: Redis 7
- **Background tasks**: Celery
- **Auth**: JWT (HS256) + TOTP-based MFA
- **Monitoring**: Prometheus, Grafana, OpenTelemetry (Jaeger)
- **Container**: Docker + docker-compose
- **CI**: GitHub Actions

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose

### Running with Docker

```bash
git clone https://github.com/krishpatel-dev/amrutam-pharmaceuticals.git
cd amrutam-pharmaceuticals
cp .env.example .env
# update .env with your secrets

docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml exec api alembic upgrade head

curl http://localhost:8000/health
```

### Running locally

```bash
python -m venv .venv
.venv\Scripts\activate   # Linux/Mac: source .venv/bin/activate

pip install -e ".[dev]"

# spin up postgres and redis separately
docker run -d -p 5432:5432 -e POSTGRES_DB=amrutam_db -e POSTGRES_PASSWORD=postgres postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## API Docs

- Swagger UI: http://localhost:8000/docs (only in development mode)
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Example Requests

### Register and login

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "Secure123!", "first_name": "John", "last_name": "Doe", "role": "patient"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "Secure123!"}'
```

### Search doctors

```bash
curl "http://localhost:8000/api/v1/search/doctors?specialty=Cardiology&max_fee=1000&sort_by=rating" \
  -H "Authorization: Bearer <token>"
```

### Book a consultation

```bash
curl -X POST http://localhost:8000/api/v1/consultations \
  -H "Authorization: Bearer <token>" \
  -H "X-Idempotency-Key: my-unique-key-001" \
  -H "Content-Type: application/json" \
  -d '{"slot_id": "<slot-uuid>", "chief_complaint": "Chest pain"}'
```

## Running Tests

```bash
# all tests
pytest tests/ -v --cov=app --cov-report=term-missing

# unit tests only (no DB needed)
pytest tests/unit/ -v

# integration tests (needs running DB)
pytest tests/integration/ -v
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `APP_SECRET_KEY` | App secret, at least 32 chars |
| `JWT_SECRET_KEY` | JWT signing secret, at least 32 chars |
| `REDIS_URL` | Redis connection string |
| `APP_ENV` | `development`, `staging`, or `production` |
| `PAYMENT_WEBHOOK_SECRET` | HMAC secret for payment webhook verification |
| `OTLP_ENDPOINT` | Jaeger OTLP endpoint (optional) |

## Monitoring

| Service | URL |
|---------|-----|
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin123) |
| Jaeger | http://localhost:16686 |
| Metrics endpoint | http://localhost:8000/metrics |

## Migrations

```bash
alembic revision --autogenerate -m "add something"
alembic upgrade head
alembic downgrade -1
```

## Project Structure

```
amrutam-pharmaceuticals/
├── app/
│   ├── api/v1/         # route handlers
│   ├── core/           # config, security, middleware, dependencies
│   ├── db/             # database engine and session
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── services/       # business logic
│   ├── repositories/   # database queries
│   ├── workers/        # Celery tasks
│   ├── observability/  # metrics, tracing, logging setup
│   └── main.py
├── migrations/         # Alembic migration scripts
├── tests/              # unit and integration tests
├── infra/              # Dockerfile, docker-compose, prometheus config
├── docs/               # design notes
└── .github/workflows/  # CI pipeline
```

## Docs

- [Architecture notes](docs/architecture.md)
- [Security notes](docs/security-checklist.md)
- [Threat model (STRIDE)](docs/threat-model.md)
- [ER diagram](docs/er-diagram.md)
- [OpenAPI 3.1 Schema](docs/openapi.json)

