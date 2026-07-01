from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Repo-relative defaults so a fresh clone works without any env file.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SQLITE_PATH = _BACKEND_ROOT / "nyx.db"
_DEFAULT_UPLOAD_DIR = _BACKEND_ROOT / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "Nyx"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # Dev defaults so `uvicorn app.main:app` runs straight out of a fresh clone.
    # MUST be overridden in production.
    SECRET_KEY: str = "dev-insecure-secret-change-me-in-production"
    ALLOWED_HOSTS: str = "*"

    # Database — defaults to a file-backed SQLite next to the app.
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_SQLITE_PATH.as_posix()}"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis — optional. If unreachable, the worker queue falls back to inline execution.
    REDIS_URL: str = "redis://localhost:6379/0"
    # auto: use Redis if reachable, else inline. inline: never use Redis. redis: require Redis.
    QUEUE_BACKEND: Literal["auto", "redis", "inline"] = "auto"

    # JWT — dev defaults; MUST be overridden in production.
    JWT_SECRET_KEY: str = "dev-insecure-jwt-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    UPLOAD_DIR: str = str(_DEFAULT_UPLOAD_DIR)
    MAX_UPLOAD_SIZE_MB: int = 20

    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str = "nyx-invoices"
    S3_REGION: str = "ap-south-1"

    # OCR — optional system deps (tesseract + poppler). If absent, OCR jobs fail
    # gracefully with extraction_notes set; the API + upload flow still work.
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    OCR_LANGUAGE: str = "eng"

    # Workers
    WORKER_CONCURRENCY: int = 4
    JOB_TIMEOUT: int = 300
    JOB_RESULT_TTL: int = 86400
    JOB_FAILURE_TTL: int = 604800

    # Reconciliation
    RECONCILIATION_TOLERANCE_PERCENT: float = 0.01
    RECONCILIATION_DUPLICATE_WINDOW_DAYS: int = 30

    # Finance approvals — invoices above this amount are held at
    # PENDING_APPROVAL instead of auto-reconciling. Single global threshold
    # for now; per-tenant config is future work (needs a tenant_config table).
    FOUNDER_APPROVAL_THRESHOLD_INR: float = 100000.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Ensure local upload dir exists for local storage backend.
    if settings.STORAGE_BACKEND == "local":
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
