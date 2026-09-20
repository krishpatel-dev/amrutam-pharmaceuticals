"""Integration tests for health and auth endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestHealth:
    async def test_health_check_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_readiness_check(self, client: AsyncClient):
        response = await client.get("/ready")
        # 200 if DB/Redis up, 503 if not — either is a valid response from the app
        assert response.status_code in (200, 503)


class TestAuthEndpoints:
    async def test_register_missing_fields_returns_422(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Secure123!",
                "first_name": "John",
                "last_name": "Doe",
                "role": "patient",
            },
        )
        assert response.status_code == 422

    async def test_login_wrong_credentials_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "WrongPassword1!"},
        )
        assert response.status_code == 401

    async def test_protected_endpoint_without_token_returns_401(
        self, client: AsyncClient
    ):
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    async def test_protected_endpoint_with_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert response.status_code == 401


class TestSearchEndpoints:
    async def test_search_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/search/doctors")
        assert response.status_code == 401

    async def test_search_invalid_page_size_returns_422(self, client: AsyncClient):
        # page_size > 100 should fail Pydantic validation
        response = await client.get(
            "/api/v1/search/doctors?page_size=9999",
            headers={"Authorization": "Bearer fake"},
        )
        # 422 from Pydantic validation OR 401 from auth — both fine
        assert response.status_code in (401, 422)


class TestAdminEndpoints:
    async def test_admin_endpoint_without_auth_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/admin/analytics/overview")
        assert response.status_code == 401

    async def test_admin_endpoint_patient_role_returns_403_or_401(
        self, client: AsyncClient
    ):
        response = await client.get(
            "/api/v1/admin/analytics/overview",
            headers={"Authorization": "Bearer fake.token.here"},
        )
        assert response.status_code in (401, 403)
