from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _build_engine():
    """Build a SQLAlchemy Engine appropriate for the configured DATABASE_URL.

    SQLite needs different engine args (no pool sizing, check_same_thread)
    and does not understand SET TIME ZONE.
    """
    if settings.is_sqlite:
        return create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
            future=True,
        )

    return create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.DEBUG,
        future=True,
    )


engine = _build_engine()


if not settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.close()
else:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
        # FK enforcement is off by default in SQLite; turn it on so ondelete
        # cascade/restrict semantics behave the same as on Postgres.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
