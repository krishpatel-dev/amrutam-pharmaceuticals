"""Pytest configuration and shared fixtures."""

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

TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/amrutam_db", "/amrutam_test"
).replace("postgresql+asyncpg://", "postgresql+asyncpg://")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create all tables once per test session, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a scoped test DB session with rollback isolation."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client with DB session override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_patient(client: AsyncClient) -> dict:
    """Register and return a patient user."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "patient@test.com",
            "password": "TestPass1!",
            "first_name": "Test",
            "last_name": "Patient",
            "role": "patient",
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest_asyncio.fixture
async def patient_token(client: AsyncClient) -> str:
    """Login a patient and return access token."""
    # Ensure patient exists
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
    data = resp.json()
    return data.get("access_token", "")


@pytest_asyncio.fixture
async def doctor_token(client: AsyncClient) -> str:
    """Register a doctor and return access token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doctor_auth@test.com",
            "password": "TestPass1!",
            "first_name": "Auth",
            "last_name": "Doctor",
            "role": "doctor",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "doctor_auth@test.com", "password": "TestPass1!"},
    )
    return resp.json().get("access_token", "")
