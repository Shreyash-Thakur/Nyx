"""Role-based access control (ADR-0004: application-layer authorization).

A single ``can(user, permission)`` function is the authorization decision point
for every interface (web today, WhatsApp / workers later), so the same rule and
the same audit story apply everywhere.

Permissions are currently derived statically from the coarse role enum. A
future DB-backed role/permission model (roadmap) slots in behind ``can()``
without touching any route — that is the point of routing every check through
this surface rather than inspecting ``user.role`` directly.
"""
from __future__ import annotations

from app.models.user import User, UserRole


class Permission:
    INVOICE_READ = "invoice:read"
    INVOICE_WRITE = "invoice:write"
    RECONCILIATION_READ = "reconciliation:read"
    RECONCILIATION_WRITE = "reconciliation:write"
    VENDOR_READ = "vendor:read"
    VENDOR_WRITE = "vendor:write"
    DASHBOARD_READ = "dashboard:read"
    AUDIT_READ = "audit:read"
    NOTIFICATION_READ = "notification:read"
    USER_MANAGE = "user:manage"
    WORKFLOW_MANAGE = "workflow:manage"
    INVOICE_APPROVE = "invoice:approve"

    @classmethod
    def all(cls) -> set[str]:
        return {
            v
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        }


_READ_PERMS = {
    Permission.INVOICE_READ,
    Permission.RECONCILIATION_READ,
    Permission.VENDOR_READ,
    Permission.DASHBOARD_READ,
    Permission.AUDIT_READ,
    Permission.NOTIFICATION_READ,
}

_OPERATE_PERMS = _READ_PERMS | {
    Permission.INVOICE_WRITE,
    Permission.RECONCILIATION_WRITE,
    Permission.VENDOR_WRITE,
}

ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: Permission.all(),
    UserRole.ACCOUNTANT: _OPERATE_PERMS,
    UserRole.VIEWER: _READ_PERMS,
}


def can(user: User, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, set())
