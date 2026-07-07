import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import DomainEvent, event_bus
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.logging import get_logger
from app.core.mail import MailMessage, get_mail_sender
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_action_token,
    hash_action_token,
    hash_password,
    verify_password,
)
from app.models.auth_token import KIND_EMAIL_VERIFICATION, KIND_PASSWORD_RESET
from app.models.user import User, UserRole
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = get_logger(__name__)

# Action-token lifetimes. Verification links are convenience, so they get a
# day; reset links are an attack target, so they get minutes.
EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(minutes=30)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)

    def _issue_tokens(self, user: User) -> tuple[TokenResponse, uuid.UUID]:
        """Mint an access+refresh pair, persisting the refresh jti server-side."""
        jti = uuid.uuid4()
        self.token_repo.create_refresh(
            user_id=user.id,
            tenant_id=user.tenant_id,
            jti=jti,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        tokens = TokenResponse(
            access_token=create_access_token(
                str(user.id),
                extra={"email": user.email, "role": user.role.value},
            ),
            refresh_token=create_refresh_token(str(user.id), str(jti)),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return tokens, jti

    def _issue_action_token(self, user: User, kind: str, ttl: timedelta) -> str:
        """Create a single-use action token; returns the raw (unhashed) token.

        The raw token exists only long enough to be mailed — it is never
        logged or persisted.
        """
        raw = generate_action_token()
        self.token_repo.create_action_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            kind=kind,
            token_hash=hash_action_token(raw),
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        return raw

    def _send_verification_mail(self, user: User, raw_token: str) -> None:
        get_mail_sender().send(
            MailMessage(
                to=user.email,
                subject="Verify your email",
                body=(
                    f"Hi {user.full_name},\n\n"
                    f"Verify your email with this token: {raw_token}\n\n"
                    "The token expires in 24 hours."
                ),
            )
        )

    def _send_reset_mail(self, user: User, raw_token: str) -> None:
        get_mail_sender().send(
            MailMessage(
                to=user.email,
                subject="Reset your password",
                body=(
                    f"Hi {user.full_name},\n\n"
                    f"Reset your password with this token: {raw_token}\n\n"
                    "The token expires in 30 minutes. If you did not request "
                    "this, you can ignore this email."
                ),
            )
        )

    def register(self, payload: RegisterRequest) -> User:
        if self.user_repo.email_exists(payload.email):
            raise ConflictError(f"Email {payload.email} is already registered")

        try:
            role = UserRole(payload.role)
        except ValueError:
            role = UserRole.ACCOUNTANT

        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=role,
            is_active=True,
            is_verified=False,
        )
        user = self.user_repo.save(user)
        event_bus.publish(
            self.db,
            DomainEvent(
                name="user.created",
                aggregate_type="user",
                aggregate_id=user.id,
                actor_id=user.id,
                tenant_id=user.tenant_id,
                payload={"description": f"New user registered: {user.email}"},
            ),
        )
        raw_token = self._issue_action_token(user, KIND_EMAIL_VERIFICATION, EMAIL_VERIFICATION_TTL)
        self._send_verification_mail(user, raw_token)
        self.db.commit()
        return user

    def login(self, payload: LoginRequest, ip_address: str | None = None) -> TokenResponse:
        user = self.user_repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        if settings.REQUIRE_VERIFIED_EMAIL_FOR_LOGIN and not user.is_verified:
            raise AuthenticationError("Email not verified")

        tokens, _ = self._issue_tokens(user)

        event_bus.publish(
            self.db,
            DomainEvent(
                name="user.logged_in",
                aggregate_type="user",
                aggregate_id=user.id,
                actor_id=user.id,
                tenant_id=user.tenant_id,
                payload={
                    "description": f"User logged in: {user.email}",
                    "ip_address": ip_address,
                },
            ),
        )
        self.db.commit()

        return tokens

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Rotate a refresh token, detecting reuse of rotated/revoked ones.

        Every refresh consumes the presented jti and issues a new one. A jti
        that was already consumed can only be presented by a replayed or
        stolen token, so all of the user's sessions are revoked (SEC-1).
        """
        try:
            payload = decode_token(refresh_token)
        except ValueError as exc:
            raise AuthenticationError("Invalid refresh token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        # Tokens minted before rotation shipped carry no jti; they are
        # unconditionally invalid (pre-production breaking change).
        try:
            jti = uuid.UUID(str(payload["jti"]))
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid refresh token") from exc

        row = self.token_repo.get_refresh_by_jti(jti)
        if row is None:
            raise AuthenticationError("Invalid refresh token")

        if row.revoked_at is not None:
            # Reuse: revoke everything this user holds and leave a trace.
            self.token_repo.revoke_all_for_user(row.user_id, row.tenant_id)
            event_bus.publish(
                self.db,
                DomainEvent(
                    name="user.refresh_reuse_detected",
                    aggregate_type="user",
                    aggregate_id=row.user_id,
                    actor_id=row.user_id,
                    tenant_id=row.tenant_id,
                    payload={
                        "description": "Refresh token reuse detected; all sessions revoked"
                    },
                ),
            )
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=str(row.user_id),
                tenant_id=str(row.tenant_id),
            )
            self.db.commit()
            raise AuthenticationError("Refresh token reuse detected")

        if self.token_repo.is_expired(row):
            raise AuthenticationError("Invalid refresh token")

        user = self.user_repo.get(row.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        tokens, new_jti = self._issue_tokens(user)
        self.token_repo.mark_rotated(row, new_jti)
        self.db.commit()
        return tokens

    def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        self.user_repo.save(user)
        # A password change invalidates every live session (SEC-1): a stolen
        # refresh token must not survive the credential it was issued under.
        self.token_repo.revoke_all_for_user(user.id, user.tenant_id)
        event_bus.publish(
            self.db,
            DomainEvent(
                name="user.password_changed",
                aggregate_type="user",
                aggregate_id=user.id,
                actor_id=user.id,
                tenant_id=user.tenant_id,
                payload={"description": "Password changed"},
            ),
        )
        self.db.commit()

    def verify_email(self, raw_token: str) -> User:
        """Consume a verification token and mark the user verified.

        One generic error for invalid/expired/used tokens — the caller learns
        nothing about which tokens exist or existed.
        """
        row = self.token_repo.get_valid_action_token(
            KIND_EMAIL_VERIFICATION, hash_action_token(raw_token)
        )
        if row is None:
            raise AuthenticationError("Invalid or expired verification token")

        user = self.user_repo.get(row.user_id)
        if user is None:
            raise AuthenticationError("Invalid or expired verification token")

        user.is_verified = True
        self.user_repo.save(user)
        self.token_repo.mark_used(row)
        event_bus.publish(
            self.db,
            DomainEvent(
                name="user.email_verified",
                aggregate_type="user",
                aggregate_id=user.id,
                actor_id=user.id,
                tenant_id=user.tenant_id,
                payload={"description": f"Email verified: {user.email}"},
            ),
        )
        self.db.commit()
        return user

    def resend_verification(self, user: User) -> None:
        if user.is_verified:
            raise ValidationError("Email is already verified")
        # Only the newest link may work: stale links in an inbox are a
        # takeover vector if the mailbox is ever compromised.
        self.token_repo.invalidate_pending(KIND_EMAIL_VERIFICATION, user.id, user.tenant_id)
        raw_token = self._issue_action_token(user, KIND_EMAIL_VERIFICATION, EMAIL_VERIFICATION_TTL)
        self._send_verification_mail(user, raw_token)
        self.db.commit()

    def forgot_password(self, email: str) -> None:
        """Start a password reset. Deliberately silent about whether the
        account exists (no user enumeration): same behavior, and the token
        generation/hash work happens on every call so timing stays similar.
        """
        raw_token = generate_action_token()
        token_hash = hash_action_token(raw_token)

        user = self.user_repo.get_by_email(email)
        if user is None or not user.is_active:
            return

        self.token_repo.invalidate_pending(KIND_PASSWORD_RESET, user.id, user.tenant_id)
        self.token_repo.create_action_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            kind=KIND_PASSWORD_RESET,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + PASSWORD_RESET_TTL,
        )
        self._send_reset_mail(user, raw_token)
        self.db.commit()

    def reset_password(self, raw_token: str, new_password: str) -> None:
        """Consume a reset token: new hash, kill every session, audit trail."""
        row = self.token_repo.get_valid_action_token(
            KIND_PASSWORD_RESET, hash_action_token(raw_token)
        )
        if row is None:
            raise AuthenticationError("Invalid or expired reset token")

        user = self.user_repo.get(row.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid or expired reset token")

        user.hashed_password = hash_password(new_password)
        self.user_repo.save(user)
        self.token_repo.mark_used(row)
        self.token_repo.revoke_all_for_user(user.id, user.tenant_id)
        # Reuses the existing password_changed event so the audit mapping
        # that already exists covers resets too.
        event_bus.publish(
            self.db,
            DomainEvent(
                name="user.password_changed",
                aggregate_type="user",
                aggregate_id=user.id,
                actor_id=user.id,
                tenant_id=user.tenant_id,
                payload={"description": "Password reset via reset token"},
            ),
        )
        self.db.commit()
