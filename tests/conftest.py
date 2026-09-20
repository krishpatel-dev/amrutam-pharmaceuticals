"""Pytest configuration and shared fixtures.

Uses the industry-standard transactional isolation pattern:
- Session-scoped engine creates all tables once.
- Each test runs inside a transaction that rolls back — no data leaks between tests.
- FastAPI's get_db dependency is overridden to inject the test session.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base, get_db
from app.main import app

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/amrutam_db", "/amrutam_test")


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop shared across the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create engine + all tables once per session, drop after all tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Each test gets its own connection wrapped in a transaction that rolls back.

    This means every test starts with a clean slate — no leftover rows.
    """
    connection = await db_engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    session = session_factory()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client with the DB session injected into FastAPI."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def patient_token(client: AsyncClient) -> str:
    """Register a patient and return their access token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "patient_auth@test.com",
            "password": "TestPass1!",
            "first_name": "Auth",
            "last_name": "Patient",
            "role": "patient",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "patient_auth@test.com", "password": "TestPass1!"},
    )
    return resp.json().get("access_token", "")


@pytest_asyncio.fixture
async def doctor_token(client: AsyncClient) -> str:
    """Register a doctor and return their access token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doctor_auth@test.com",
            "password": "DocPass1!",
            "first_name": "Auth",
            "last_name": "Doctor",
            "role": "doctor",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "doctor_auth@test.com", "password": "DocPass1!"},
    )
    return resp.json().get("access_token", "")
