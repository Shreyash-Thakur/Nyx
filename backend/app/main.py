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
    logger.info("ledgerflow_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    if not check_db_connection():
        logger.error("database_unreachable")
    else:
        logger.info("database_connected")
    yield
    logger.info("ledgerflow_shutdown")


app = FastAPI(
    title="LedgerFlow API",
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
    try:
        from app.workers.queue import get_redis
        get_redis().ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    overall = "healthy" if db_ok and redis_ok else "degraded"
    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": {"database": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"},
    }


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}
