"""Integration tests for authentication endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestRegister:
    async def test_register_patient_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newpatient@example.com",
                "password": "Secure123!",
                "first_name": "John",
                "last_name": "Doe",
                "role": "patient",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["email"] == "newpatient@example.com"
        assert data["data"]["role"] == "patient"

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {
            "email": "dup@example.com",
            "password": "Secure123!",
            "first_name": "A",
            "last_name": "B",
            "role": "patient",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "DUPLICATE_EMAIL"

    async def test_register_weak_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "password",  # No uppercase, digit, or special char
                "first_name": "A",
                "last_name": "B",
                "role": "patient",
            },
        )
        assert resp.status_code == 422

    async def test_register_invalid_role_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@example.com",
                "password": "Secure123!",
                "first_name": "A",
                "last_name": "B",
                "role": "admin",  # Not allowed via registration
            },
        )
        assert resp.status_code == 422

    async def test_register_doctor_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dr.smith@example.com",
                "password": "DocPass1!",
                "first_name": "Jane",
                "last_name": "Smith",
                "role": "doctor",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["role"] == "doctor"


class TestLogin:
    async def test_login_success_returns_tokens(self, client: AsyncClient):
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login_test@example.com",
                "password": "LoginPass1!",
                "first_name": "Login",
                "last_name": "Test",
                "role": "patient",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login_test@example.com", "password": "LoginPass1!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "RightPass1!",
                "first_name": "A",
                "last_name": "B",
                "role": "patient",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpass@example.com", "password": "WrongPass1!"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_nonexistent_email_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "SomePass1!"},
        )
        assert resp.status_code == 401


class TestTokenRefresh:
    async def test_refresh_returns_new_access_token(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh_test@example.com",
                "password": "RefreshPass1!",
                "first_name": "R",
                "last_name": "T",
                "role": "patient",
            },
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh_test@example.com", "password": "RefreshPass1!"},
        )
        refresh_token = login.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_with_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not.a.real.token"}
        )
        assert resp.status_code == 401


class TestProtectedEndpoints:
    async def test_me_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401

    async def test_me_with_valid_token_returns_user(self, client: AsyncClient, patient_token: str):
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] is not None
