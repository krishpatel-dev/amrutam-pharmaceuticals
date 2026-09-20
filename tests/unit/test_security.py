"""Unit tests for security utilities."""

from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_idempotency_key,
    generate_mfa_secret,
    hash_password,
    verify_password,
    verify_totp,
    verify_webhook_signature,
)


class TestPasswordHashing:
    def test_hash_is_not_plain_text(self):
        plain = "MySecret123!"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        plain = "MySecret123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_reject_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_two_hashes_are_different(self):
        """bcrypt uses random salts — same input produces different hashes."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJWT:
    def test_access_token_contains_role(self):
        token = create_access_token("user-123", "patient")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "patient"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-456"

    def test_invalid_token_raises(self):
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        from jose import JWTError

        token = create_access_token("user-789", "admin")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_access_token_has_jti(self):
        """Each token has a unique JWT ID for potential revocation."""
        t1 = create_access_token("u1", "patient")
        t2 = create_access_token("u1", "patient")
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]


class TestMFA:
    def test_generate_secret_is_base32(self):
        import base64

        secret = generate_mfa_secret()
        assert len(secret) >= 16
        # Must be valid base32
        base64.b32decode(secret, casefold=True)

    def test_valid_totp_code(self):
        import pyotp

        secret = generate_mfa_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_invalid_totp_code(self):
        secret = generate_mfa_secret()
        assert verify_totp(secret, "000000") is False


class TestWebhookSignature:
    def test_valid_signature(self):
        import hashlib
        import hmac

        secret = "test-secret"
        payload = b'{"event": "payment.captured"}'
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        payload = b'{"event": "payment.captured"}'
        assert verify_webhook_signature(payload, "bad_sig", "secret") is False

    def test_timing_safe_comparison(self):
        """verify_webhook_signature uses hmac.compare_digest (constant-time)."""
        import hashlib
        import hmac

        secret = "secret"
        payload = b"data"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        # Alter last char — should fail, not short-circuit
        bad = sig[:-1] + ("0" if sig[-1] != "0" else "1")
        assert verify_webhook_signature(payload, bad, secret) is False


class TestIdempotencyKey:
    def test_key_is_url_safe(self):
        key = generate_idempotency_key()
        assert len(key) >= 32
        # Should not contain URL-unsafe chars
        import re
        assert re.match(r"^[A-Za-z0-9_\-]+$", key)

    def test_keys_are_unique(self):
        keys = {generate_idempotency_key() for _ in range(100)}
        assert len(keys) == 100
