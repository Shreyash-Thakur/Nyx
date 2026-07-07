"""Server-side auth token state (SEC-1).

Two small tables back the auth lifecycle:

* ``refresh_tokens`` — one row per issued refresh JWT (keyed by its ``jti``).
  Rotation marks the old row and links the replacement; a presented token
  whose row is already revoked/rotated is proof of theft-or-replay and
  triggers revocation of every session for that user.
* ``auth_action_tokens`` — single-use, time-boxed tokens for email
  verification and password reset. Only the SHA-256 of the raw token is
  stored, so the database never contains a usable link.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin

# Action-token kinds. Plain strings (not an Enum column) so adding a kind
# never needs a migration.
KIND_EMAIL_VERIFICATION = "email_verification"
KIND_PASSWORD_RESET = "password_reset"


class RefreshToken(TenantMixin, BaseModel):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[uuid.UUID] = mapped_column(GUID(), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set on rotation: which jti superseded this one. A revoked row WITH a
    # successor was rotated normally; presenting it again is token reuse.
    replaced_by_jti: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    def __repr__(self) -> str:
        return f"<RefreshToken {self.jti} user={self.user_id}>"


class AuthActionToken(TenantMixin, BaseModel):
    __tablename__ = "auth_action_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AuthActionToken {self.kind} user={self.user_id}>"
