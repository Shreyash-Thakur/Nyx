from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError, forbidden, unauthorized
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not credentials:
        raise unauthorized()
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise unauthorized("Invalid or expired token")

    if payload.get("type") != "access":
        raise unauthorized("Invalid token type")

    user = UserRepository(db).get(payload["sub"])
    if not user or not user.is_active:
        raise unauthorized("User not found or inactive")
    return user


def require_roles(*roles: UserRole):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise forbidden(f"Required roles: {[r.value for r in roles]}")
        return user

    return checker


def require(permission: str):
    """Route dependency that enforces a single permission via can().

    Use as ``dependencies=[Depends(require(Permission.INVOICE_WRITE))]`` so it
    gates the route without altering the handler signature.
    """
    from app.core.rbac import can

    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not can(user, permission):
            raise forbidden(f"Missing permission: {permission}")
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DBSession = Annotated[Session, Depends(get_db)]
