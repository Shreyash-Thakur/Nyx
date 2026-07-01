from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import DomainEvent, event_bus
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

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
        self.db.commit()
        return user

    def login(self, payload: LoginRequest, ip_address: str | None = None) -> TokenResponse:
        user = self.user_repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        access_token = create_access_token(
            str(user.id),
            extra={"email": user.email, "role": user.role.value},
        )
        refresh_token = create_refresh_token(str(user.id))

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

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError as exc:
            raise AuthenticationError("Invalid refresh token") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        user = self.user_repo.get(payload["sub"])
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        access_token = create_access_token(
            str(user.id),
            extra={"email": user.email, "role": user.role.value},
        )
        new_refresh = create_refresh_token(str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        self.user_repo.save(user)
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
