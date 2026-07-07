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
