"""Pytest configuration and shared fixtures for test isolation and DB management.

Architecture:
- Test engine uses NullPool to ensure connections are opened on demand and closed
  immediately, eliminating cross-event-loop and concurrency issues in asyncpg.
- Tables are created once at the start of the test session and dropped at the end.
- Between each test, an autouse fixture truncates all tables (with CASCADE) to ensure
  strict data isolation and a clean slate.
- FastAPI's get_db dependency is overridden with a per-request session factory,
  ensuring each HTTP request gets its own AsyncSession that commits on success
  and closes cleanly, matching production behavior and preventing asyncpg concurrency conflicts.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 - ensures all ORM models are registered on Base.metadata
from app.core.config import settings
from app.db.base import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or settings.DATABASE_URL.replace(
    "/amrutam_db", "/amrutam_test"
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create all tables once per test session, drop after session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(db_engine):
    """Clean all tables before and after each test to guarantee strict isolation."""
    if db_engine is not None:
        async with test_engine.begin() as conn:
            table_names = ", ".join(
                f'"{table.name}"' for table in Base.metadata.sorted_tables
            )
            if table_names:
                await conn.execute(
                    text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE;")
                )
    yield
    if db_engine is not None:
        async with test_engine.begin() as conn:
            table_names = ", ".join(
                f'"{table.name}"' for table in Base.metadata.sorted_tables
            )
            if table_names:
                await conn.execute(
                    text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE;")
                )


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a dedicated async DB session for tests that directly need one."""
    if db_engine is None:
        yield None  # type: ignore[misc]
        return
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client with isolated per-request DB sessions."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

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
