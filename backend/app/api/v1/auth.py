from fastapi import APIRouter, Request

from app.core.exceptions import bad_request, conflict, unauthorized
from app.core.exceptions import AuthenticationError, ConflictError
from app.dependencies import CurrentUser, DBSession
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: DBSession):
    """Register a new user account."""
    try:
        user = AuthService(db).register(payload)
    except ConflictError as exc:
        raise conflict(exc.message)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DBSession):
    """Authenticate and receive JWT tokens."""
    try:
        tokens = AuthService(db).login(
            payload,
            ip_address=request.client.host if request.client else None,
        )
    except AuthenticationError as exc:
        raise unauthorized(exc.message)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DBSession):
    """Obtain a new access token using a refresh token."""
    try:
        tokens = AuthService(db).refresh_tokens(payload.refresh_token)
    except AuthenticationError as exc:
        raise unauthorized(exc.message)
    return tokens


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser):
    """Return the authenticated user's profile."""
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Change the current user's password."""
    try:
        AuthService(db).change_password(
            current_user, payload.current_password, payload.new_password
        )
    except AuthenticationError as exc:
        raise bad_request(exc.message)
    return MessageResponse(message="Password changed successfully")
