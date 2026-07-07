from fastapi import APIRouter, Request

from app.core.exceptions import bad_request, conflict, unauthorized
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.limiter import limiter
from app.dependencies import CurrentUser, DBSession
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: DBSession):
    """Register a new user account."""
    try:
        user = AuthService(db).register(payload)
    except ConflictError as exc:
        raise conflict(exc.message)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: DBSession):
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


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit("10/minute")
def verify_email(request: Request, payload: VerifyEmailRequest, db: DBSession):
    """Verify an email address with a mailed single-use token."""
    try:
        AuthService(db).verify_email(payload.token)
    except AuthenticationError as exc:
        raise unauthorized(exc.message)
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit("3/minute")
def resend_verification(request: Request, current_user: CurrentUser, db: DBSession):
    """Send a fresh verification token; older pending tokens stop working."""
    try:
        AuthService(db).resend_verification(current_user)
    except ValidationError as exc:
        raise bad_request(exc.message)
    return MessageResponse(message="Verification email sent")


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
@limiter.limit("3/minute")
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: DBSession):
    """Start a password reset. Response is identical whether or not the
    account exists — no user enumeration."""
    AuthService(db).forgot_password(payload.email)
    return MessageResponse(message="If the account exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def reset_password(request: Request, payload: ResetPasswordRequest, db: DBSession):
    """Complete a password reset with a mailed single-use token."""
    try:
        AuthService(db).reset_password(payload.token, payload.new_password)
    except AuthenticationError as exc:
        raise unauthorized(exc.message)
    return MessageResponse(message="Password reset successfully")
