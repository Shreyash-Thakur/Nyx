import time
import uuid

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


# Avoid bare Any import error
from typing import Any  # noqa: E402
