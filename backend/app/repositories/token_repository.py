"""All DB access for refresh + action tokens (SEC-1).

Validity (unused / unexpired) is decided in Python after fetching by the
unique key rather than in SQL: SQLite returns naive datetimes for
timezone-aware columns, so datetime comparisons in the WHERE clause are not
portable, and every lookup here is already by a unique index.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth_token import AuthActionToken, RefreshToken


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB datetimes: SQLite hands back naive UTC, Postgres aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class TokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── refresh tokens ──────────────────────────────────────────────────

    def create_refresh(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        jti: uuid.UUID,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id, tenant_id=tenant_id, jti=jti, expires_at=expires_at
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_refresh_by_jti(self, jti: uuid.UUID) -> RefreshToken | None:
        # jti is globally unique; the caller resolves tenant/user from the row.
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        return self.db.scalar(stmt)

    def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        self.db.flush()

    def mark_rotated(self, token: RefreshToken, replaced_by_jti: uuid.UUID) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        token.replaced_by_jti = replaced_by_jti
        self.db.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Kill every live session for a user (password change/reset, reuse)."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.tenant_id == tenant_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount or 0

    @staticmethod
    def is_expired(token: RefreshToken | AuthActionToken) -> bool:
        return _as_utc(token.expires_at) <= datetime.now(timezone.utc)

    # ── action tokens (email verification / password reset) ────────────

    def create_action_token(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        kind: str,
        token_hash: str,
        expires_at: datetime,
    ) -> AuthActionToken:
        token = AuthActionToken(
            user_id=user_id,
            tenant_id=tenant_id,
            kind=kind,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_valid_action_token(self, kind: str, token_hash: str) -> AuthActionToken | None:
        """Return the token only if it is the right kind, unused and unexpired."""
        stmt = select(AuthActionToken).where(
            AuthActionToken.kind == kind,
            AuthActionToken.token_hash == token_hash,
        )
        token = self.db.scalar(stmt)
        if token is None or token.used_at is not None or self.is_expired(token):
            return None
        return token

    def mark_used(self, token: AuthActionToken) -> None:
        token.used_at = datetime.now(timezone.utc)
        self.db.flush()

    def invalidate_pending(self, kind: str, user_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Mark older unused tokens used so only the newest link works."""
        stmt = (
            update(AuthActionToken)
            .where(
                AuthActionToken.kind == kind,
                AuthActionToken.user_id == user_id,
                AuthActionToken.tenant_id == tenant_id,
                AuthActionToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(timezone.utc))
        )
        result = self.db.execute(stmt)
        self.db.flush()
        return result.rowcount or 0
