"""Unit test conftest — no database required.

Overrides the session-scoped database fixture from the root conftest so that
unit tests can run without a running PostgreSQL instance.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
async def setup_database():  # type: ignore[override]
    """No-op override — unit tests do not touch the database."""
    yield
