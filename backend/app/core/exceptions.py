from fastapi import HTTPException, status


class LedgerFlowError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(LedgerFlowError):
    pass


class ConflictError(LedgerFlowError):
    pass


class ValidationError(LedgerFlowError):
    pass


class AuthenticationError(LedgerFlowError):
    pass


class AuthorizationError(LedgerFlowError):
    pass


class StorageError(LedgerFlowError):
    pass


class ProcessingError(LedgerFlowError):
    pass


# ── HTTP exception factories ────────────────────────────────────────────────

def not_found(resource: str, identifier: str | None = None) -> HTTPException:
    detail = f"{resource} not found"
    if identifier:
        detail = f"{resource} '{identifier}' not found"
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def unauthorized(message: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(message: str = "Insufficient permissions") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
