"""Auth lifecycle hardening (SEC-1/SEC-3): rotation, revocation, reuse
detection, email verification, password reset, production secret guardrails."""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings


def _login(client, email="admin@nyxapp.com", password="Admin1234"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()


def _refresh(client, refresh_token):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


class TestRefreshRotation:
    def test_rotation_returns_new_working_pair(self, client, admin_user):
        first = _login(client)
        resp = _refresh(client, first["refresh_token"])
        assert resp.status_code == 200
        rotated = resp.json()
        assert rotated["refresh_token"] != first["refresh_token"]

        # The rotated pair is fully live: access works, refresh rotates again.
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {rotated['access_token']}"},
        )
        assert me.status_code == 200
        assert _refresh(client, rotated["refresh_token"]).status_code == 200

    def test_old_refresh_stops_working_after_rotation(self, client, admin_user):
        first = _login(client)
        assert _refresh(client, first["refresh_token"]).status_code == 200
        resp = _refresh(client, first["refresh_token"])
        assert resp.status_code == 401

    def test_reuse_revokes_all_sessions(self, client, db, admin_user):
        session_a = _login(client)
        session_b = _login(client)
        rotated = _refresh(client, session_a["refresh_token"]).json()

        # Replaying the consumed token is reuse: 401 + every session dies.
        resp = _refresh(client, session_a["refresh_token"])
        assert resp.status_code == 401
        assert "reuse" in resp.json()["detail"].lower()
        assert _refresh(client, rotated["refresh_token"]).status_code == 401
        assert _refresh(client, session_b["refresh_token"]).status_code == 401

        # And it leaves a durable trace in the event log.
        from app.models.event import Event

        names = [e.name for e in db.query(Event).all()]
        assert "user.refresh_reuse_detected" in names

    def test_refresh_without_jti_claim_rejected(self, client, admin_user):
        payload = {
            "sub": str(admin_user.id),
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "type": "refresh",
        }
        legacy = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        assert _refresh(client, legacy).status_code == 401

    def test_refresh_with_unknown_jti_rejected(self, client, admin_user):
        import uuid

        payload = {
            "sub": str(admin_user.id),
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
        }
        forged = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        assert _refresh(client, forged).status_code == 401


class TestRevocation:
    def test_password_change_revokes_refresh_tokens(self, client, admin_user):
        tokens = _login(client)
        resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin1234", "new_password": "NewPass1234"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert _refresh(client, tokens["refresh_token"]).status_code == 401
        # The new credential still logs in fine.
        _login(client, password="NewPass1234")

    def test_deactivated_user_refresh_rejected(self, client, db, admin_user):
        tokens = _login(client)
        admin_user.is_active = False
        db.flush()
        assert _refresh(client, tokens["refresh_token"]).status_code == 401


@pytest.fixture()
def outbox(monkeypatch):
    """Capture outbound mail so tests can read the raw action tokens."""
    sent = []

    class _Recorder:
        def send(self, message):
            sent.append(message)

    monkeypatch.setattr("app.services.auth_service.get_mail_sender", lambda: _Recorder())
    return sent


def _token_from(mail):
    return mail.body.split("token: ")[1].split()[0]


def _register(client, email="verifyme@test.com", password="Secure1234"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Verify Me", "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


class TestEmailVerification:
    def test_verify_email_happy_path(self, client, db, outbox):
        _register(client)
        assert len(outbox) == 1
        token = _token_from(outbox[0])

        resp = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 200

        from app.models.user import User

        user = db.query(User).filter_by(email="verifyme@test.com").one()
        assert user.is_verified is True

    def test_verification_token_single_use(self, client, outbox):
        _register(client)
        token = _token_from(outbox[0])
        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 401

    def test_garbage_verification_token_rejected(self, client):
        resp = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
        assert resp.status_code == 401

    def test_expired_verification_token_rejected(self, client, db, outbox):
        _register(client)
        token = _token_from(outbox[0])

        from app.models.auth_token import AuthActionToken

        row = db.query(AuthActionToken).filter_by(kind="email_verification").one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()

        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 401

    def test_resend_invalidates_older_token(self, client, outbox):
        _register(client)
        tokens = _login(client, email="verifyme@test.com", password="Secure1234")

        resp = client.post(
            "/api/v1/auth/resend-verification",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert len(outbox) == 2

        old_token, new_token = _token_from(outbox[0]), _token_from(outbox[1])
        assert client.post("/api/v1/auth/verify-email", json={"token": old_token}).status_code == 401
        assert client.post("/api/v1/auth/verify-email", json={"token": new_token}).status_code == 200

    def test_resend_when_already_verified(self, client, admin_user, auth_headers):
        resp = client.post("/api/v1/auth/resend-verification", headers=auth_headers)
        assert resp.status_code == 400

    def test_login_blocked_for_unverified_only_when_required(
        self, client, outbox, monkeypatch
    ):
        _register(client)
        monkeypatch.setattr(settings, "REQUIRE_VERIFIED_EMAIL_FOR_LOGIN", True)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "verifyme@test.com", "password": "Secure1234"},
        )
        assert resp.status_code == 401
        assert "not verified" in resp.json()["detail"].lower()

        # Verifying unblocks login while the flag stays on.
        token = _token_from(outbox[0])
        assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
        _login(client, email="verifyme@test.com", password="Secure1234")

    def test_login_allowed_for_unverified_when_not_required(self, client, outbox):
        _register(client)
        _login(client, email="verifyme@test.com", password="Secure1234")


class TestPasswordReset:
    def test_forgot_password_response_identical_for_unknown_email(
        self, client, admin_user, outbox
    ):
        known = client.post(
            "/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"}
        )
        unknown = client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.com"}
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        # But only the real account got mail.
        assert len(outbox) == 1
        assert outbox[0].to == "admin@nyxapp.com"

    def test_reset_password_happy_path(self, client, admin_user, outbox):
        pre_reset = _login(client)

        client.post("/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"})
        token = _token_from(outbox[0])
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Reset1234"},
        )
        assert resp.status_code == 200

        # Old password dead, old sessions dead, new password works.
        old_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@nyxapp.com", "password": "Admin1234"},
        )
        assert old_login.status_code == 401
        assert _refresh(client, pre_reset["refresh_token"]).status_code == 401
        _login(client, password="Reset1234")

    def test_reset_token_single_use(self, client, admin_user, outbox):
        client.post("/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"})
        token = _token_from(outbox[0])
        first = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Reset1234"},
        )
        assert first.status_code == 200
        second = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Other1234"},
        )
        assert second.status_code == 401

    def test_newer_reset_request_invalidates_older_token(self, client, admin_user, outbox):
        client.post("/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"})
        client.post("/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"})
        old_token, new_token = _token_from(outbox[0]), _token_from(outbox[1])

        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": old_token, "new_password": "Reset1234"},
        )
        assert resp.status_code == 401
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": new_token, "new_password": "Reset1234"},
        )
        assert resp.status_code == 200

    def test_reset_rejects_weak_password(self, client, admin_user, outbox):
        client.post("/api/v1/auth/forgot-password", json={"email": "admin@nyxapp.com"})
        token = _token_from(outbox[0])
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "weak"},
        )
        assert resp.status_code == 422


class TestProductionSecretGuardrails:
    """SEC-3: production must not boot on dev-default or weak signing keys.

    Settings are constructed directly with explicit kwargs and _env_file=None
    so neither a developer .env nor the conftest env vars interfere.
    """

    _DEV_SECRET = "dev-insecure-secret-change-me-in-production"
    _DEV_JWT = "dev-insecure-jwt-secret-change-me-in-production"

    def test_production_with_dev_defaults_refuses_to_boot(self):
        from pydantic import ValidationError as PydanticValidationError

        from app.config import Settings

        with pytest.raises(PydanticValidationError, match="SECRET_KEY"):
            Settings(
                APP_ENV="production",
                SECRET_KEY=self._DEV_SECRET,
                JWT_SECRET_KEY=self._DEV_JWT,
                _env_file=None,
            )

    def test_production_with_short_secret_refuses_to_boot(self):
        from pydantic import ValidationError as PydanticValidationError

        from app.config import Settings

        with pytest.raises(PydanticValidationError, match="JWT_SECRET_KEY"):
            Settings(
                APP_ENV="production",
                SECRET_KEY="s" * 48,
                JWT_SECRET_KEY="too-short",
                _env_file=None,
            )

    def test_production_with_strong_secrets_boots(self):
        from app.config import Settings

        cfg = Settings(
            APP_ENV="production",
            SECRET_KEY="s" * 48,
            JWT_SECRET_KEY="j" * 48,
            _env_file=None,
        )
        assert cfg.is_production

    def test_development_stays_permissive_with_dev_defaults(self):
        from app.config import Settings

        cfg = Settings(
            APP_ENV="development",
            SECRET_KEY=self._DEV_SECRET,
            JWT_SECRET_KEY=self._DEV_JWT,
            _env_file=None,
        )
        assert not cfg.is_production

    def test_access_token_ttl_default_is_15_minutes(self):
        from app.config import Settings

        cfg = Settings(_env_file=None)
        assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 15
