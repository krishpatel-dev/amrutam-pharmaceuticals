"""Integration tests for booking and consultation lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str, role: str) -> str:
    """Helper: register user and return access token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "BookTest1!",
            "first_name": "Test",
            "last_name": "User",
            "role": role,
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "BookTest1!"},
    )
    return resp.json().get("access_token", "")


async def _create_doctor_and_slot(client: AsyncClient, doctor_token: str) -> dict:
    """Helper: create doctor profile, verify, and create a slot."""
    # Create doctor profile
    await client.post(
        "/api/v1/doctors/me",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "specialty": "General Medicine",
            "license_number": f"LIC-{datetime.now().timestamp()}",
            "consultation_fee": "500.00",
            "years_experience": 5,
        },
    )

    # Create a future slot
    future_start = datetime.now(UTC) + timedelta(hours=2)
    future_end = future_start + timedelta(minutes=30)
    slot_resp = await client.post(
        "/api/v1/availability",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "slots": [
                {
                    "start_time": future_start.isoformat(),
                    "end_time": future_end.isoformat(),
                    "duration_minutes": 30,
                }
            ]
        },
    )
    return slot_resp.json()["data"][0]


class TestBooking:
    async def test_patient_can_book_slot(self, client: AsyncClient):
        patient_token = await _register_and_login(client, "book_patient@test.com", "patient")
        doctor_token = await _register_and_login(client, "book_doctor@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        resp = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"slot_id": slot["id"], "chief_complaint": "Headache"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["status"] == "scheduled"
        assert data["slot_id"] == slot["id"]

    async def test_idempotent_booking(self, client: AsyncClient):
        """Same idempotency key returns same consultation."""
        patient_token = await _register_and_login(client, "idem_patient@test.com", "patient")
        doctor_token = await _register_and_login(client, "idem_doctor@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        key = "test-idem-key-12345"
        headers = {
            "Authorization": f"Bearer {patient_token}",
            "X-Idempotency-Key": key,
        }

        r1 = await client.post(
            "/api/v1/consultations",
            headers=headers,
            json={"slot_id": slot["id"]},
        )
        r2 = await client.post(
            "/api/v1/consultations",
            headers=headers,
            json={"slot_id": slot["id"]},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]

    async def test_doctor_cannot_book_as_patient(self, client: AsyncClient):
        doctor_token = await _register_and_login(client, "dr_book_fail@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        resp = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"slot_id": slot["id"]},
        )
        assert resp.status_code == 403

    async def test_double_booking_prevented(self, client: AsyncClient):
        """Two patients trying to book the same slot — second must fail."""
        patient1_token = await _register_and_login(client, "p1_race@test.com", "patient")
        patient2_token = await _register_and_login(client, "p2_race@test.com", "patient")
        doctor_token = await _register_and_login(client, "dr_race@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        r1 = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {patient1_token}"},
            json={"slot_id": slot["id"]},
        )
        r2 = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {patient2_token}"},
            json={"slot_id": slot["id"]},
        )

        statuses = {r1.status_code, r2.status_code}
        # One succeeds (201), one fails (409)
        assert 201 in statuses
        assert 409 in statuses or 400 in statuses


class TestConsultationLifecycle:
    async def test_doctor_starts_and_ends_consultation(self, client: AsyncClient):
        patient_token = await _register_and_login(client, "lc_patient@test.com", "patient")
        doctor_token = await _register_and_login(client, "lc_doctor@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        # Book
        booking = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"slot_id": slot["id"]},
        )
        consult_id = booking.json()["data"]["id"]

        # Start
        start_resp = await client.put(
            f"/api/v1/consultations/{consult_id}/start",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["data"]["status"] == "in_progress"

        # End
        end_resp = await client.put(
            f"/api/v1/consultations/{consult_id}/end",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert end_resp.status_code == 200
        assert end_resp.json()["data"]["status"] == "completed"

    async def test_patient_can_cancel_scheduled_consultation(self, client: AsyncClient):
        patient_token = await _register_and_login(client, "cancel_p@test.com", "patient")
        doctor_token = await _register_and_login(client, "cancel_d@test.com", "doctor")
        slot = await _create_doctor_and_slot(client, doctor_token)

        booking = await client.post(
            "/api/v1/consultations",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"slot_id": slot["id"]},
        )
        consult_id = booking.json()["data"]["id"]

        cancel_resp = await client.put(
            f"/api/v1/consultations/{consult_id}/cancel",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"reason": "Change of plans"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["data"]["status"] == "cancelled"
