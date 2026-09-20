"""Integration test conftest.

These tests run against the real FastAPI app using httpx.AsyncClient.
A live database is NOT required for HTTP-layer tests (schema validation,
auth checks, etc.). DB-dependent tests should explicitly request the
`setup_database` fixture from the root conftest.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """HTTP client wired directly to the FastAPI app — no network needed."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
