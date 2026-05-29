import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "full_name": "New User",
                "password": "Secure1234",
                "role": "accountant",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@test.com"
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client, admin_user):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@nyx.test",
                "full_name": "Duplicate",
                "password": "Secure1234",
            },
        )
        assert resp.status_code == 409

    def test_register_weak_password(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@test.com", "full_name": "Weak", "password": "short"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, admin_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@nyx.test", "password": "Admin1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@nyx.test", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "Whatever1"},
        )
        assert resp.status_code == 401


class TestProtectedRoute:
    def test_me_authenticated(self, client, admin_user, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@nyx.test"

    def test_me_unauthenticated(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token"})
        assert resp.status_code == 401
