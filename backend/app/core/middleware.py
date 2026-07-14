import time
import uuid
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("unhandled_exception", exc_info=exc)
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request_completed",
                status_code=response.status_code if "response" in dir() else 500,
                duration_ms=elapsed_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline security response headers (SEC-5).

    The API serves JSON, so the CSP is a deny-everything default that only
    matters if a response is ever coerced into a document context; the
    /docs Swagger UI is exempted because it legitimately loads its own
    scripts and styles.
    """

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "Cache-Control": "no-store",
    }
    _DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(self._DOC_PATHS):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            return response
        for header, value in self._HEADERS.items():
            response.headers.setdefault(header, value)
        return response
