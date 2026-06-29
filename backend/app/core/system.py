"""System principal.

Background jobs (auto-reconciliation, future workflow actions) act on behalf
of the platform itself rather than a logged-in user. They still need a real
``users`` row so foreign keys (``reconciliation_records.matched_by``,
``audit_logs.user_id``) and audit attribution stay intact.

``ensure_system_user`` is idempotent: it returns the existing system user or
creates it. The account is deactivated so it can never authenticate.
"""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User, UserRole

SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_USER_EMAIL = "system@nyx.internal"


def ensure_system_user(db: Session) -> User:
    user = db.get(User, SYSTEM_USER_ID)
    if user is not None:
        return user

    user = User(
        id=SYSTEM_USER_ID,
        email=SYSTEM_USER_EMAIL,
        full_name="Nyx System",
        # Valid-format but unknowable hash; the account is also deactivated.
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.ADMIN,
        is_active=False,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user
