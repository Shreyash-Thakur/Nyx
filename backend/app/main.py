from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.database import check_db_connection

configure_logging()

from app.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nyx_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    if not check_db_connection():
        logger.error("database_unreachable")
    else:
        logger.info("database_connected")
    yield
    logger.info("nyx_shutdown")


app = FastAPI(
    title="Nyx API",
    description=(
        "Finance operations and invoice reconciliation platform. "
        "Upload invoices, extract structured data via OCR, and reconcile against records."
    ),
    version=settings.APP_VERSION,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Event subscribers ─────────────────────────────────────────────────────────
# Registered at import time (not inside `lifespan`) so the process-wide event
# bus singleton gets exactly one subscription regardless of how many times a
# TestClient enters/exits the lifespan context within one process.
from app.core.events import audit_subscriber, notification_subscriber  # noqa: E402

audit_subscriber.register()
notification_subscriber.register()

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = (
    ["*"] if not settings.is_production
    else [o.strip() for o in settings.ALLOWED_HOSTS.split(",")]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging ───────────────────────────────────────────────────────────
from app.core.middleware import RequestLoggingMiddleware  # noqa: E402

app.add_middleware(RequestLoggingMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", path=str(request.url), error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Health endpoints ─────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], include_in_schema=False)
def health_check():
    db_ok = check_db_connection()

    # Redis is only *required* in explicit redis mode. In inline mode it is
    # intentionally absent (the queue runs in-process), and in auto mode its
    # absence is a supported fallback -- so neither should make a correctly
    # configured deployment report "degraded" (which would fail a readiness
    # probe on the default zero-dependency setup).
    backend = settings.QUEUE_BACKEND
    redis_required = backend == "redis"
    try:
        from app.workers.queue import get_redis
        get_redis().ping()
        redis_state = "ok"
    except Exception:
        redis_state = "unavailable"

    queue_ok = redis_state == "ok" or not redis_required
    overall = "healthy" if db_ok and queue_ok else "degraded"
    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": {
            "database": "ok" if db_ok else "error",
            "queue_backend": backend,
            "redis": redis_state if redis_required else f"{redis_state} (not required)",
        },
    }


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}
