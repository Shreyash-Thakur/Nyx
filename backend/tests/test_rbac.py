"""RBAC: permission-based authorization (one can() surface for every interface).

Today permissions are derived from the coarse role enum; the can()/require()
surface is what endpoints gate on, so a future DB-backed role model is a
swap behind this function rather than a rewrite of every route.
"""
import pytest

from app.core.rbac import ROLE_PERMISSIONS, Permission, can
from app.models.user import User, UserRole


def _user(role: UserRole) -> User:
    return User(email=f"{role.value}@x.com", full_name=role.value, hashed_password="x", role=role)


def test_admin_can_do_everything():
    admin = _user(UserRole.ADMIN)
    for perm in Permission.all():
        assert can(admin, perm)


def test_viewer_is_read_only():
    viewer = _user(UserRole.VIEWER)
    assert can(viewer, Permission.INVOICE_READ)
    assert not can(viewer, Permission.INVOICE_WRITE)
    assert not can(viewer, Permission.RECONCILIATION_WRITE)
    assert not can(viewer, Permission.VENDOR_WRITE)


def test_accountant_can_operate_but_not_manage_users():
    acc = _user(UserRole.ACCOUNTANT)
    assert can(acc, Permission.INVOICE_WRITE)
    assert can(acc, Permission.RECONCILIATION_WRITE)
    assert can(acc, Permission.VENDOR_WRITE)
    assert not can(acc, Permission.USER_MANAGE)


# ── API enforcement ──────────────────────────────────────────────────────────

@pytest.fixture()
def viewer_token(client, db):
    from app.core.security import hash_password

    db.add(User(
        email="viewer@nyxapp.com", full_name="Viewer",
        hashed_password=hash_password("Viewer1234"),
        role=UserRole.VIEWER, is_active=True,
    ))
    db.flush()
    resp = client.post("/api/v1/auth/login", json={"email": "viewer@nyxapp.com", "password": "Viewer1234"})
    return resp.json()["access_token"]


def test_viewer_forbidden_from_creating_vendor(client, viewer_token):
    resp = client.post(
        "/api/v1/vendors",
        json={"name": "Acme"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_viewer_can_read_vendors(client, viewer_token):
    resp = client.get("/api/v1/vendors", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 200


def test_admin_can_create_vendor(client, auth_headers):
    resp = client.post("/api/v1/vendors", json={"name": "Acme"}, headers=auth_headers)
    assert resp.status_code == 201
