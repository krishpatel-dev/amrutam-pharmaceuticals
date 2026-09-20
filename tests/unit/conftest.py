"""Unit test conftest — no database required.

Unit tests only test pure logic (JWT, hashing, etc.) and don't need
a real database connection. We override the fixtures that would try to
connect to Postgres so unit tests can run anywhere without infrastructure.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def db_engine():  # type: ignore[override]
    """No-op — unit tests don't use a database engine."""
    yield None


@pytest_asyncio.fixture
async def client() -> AsyncClient:  # type: ignore[override]
    """Lightweight client with no DB injection — unit tests don't need it."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
