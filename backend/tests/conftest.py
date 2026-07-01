"""Shared pytest fixtures.

Defaults to in-memory SQLite so a fresh clone can run `pytest` with no
external services. Override with TEST_DATABASE_URL to point at Postgres.
"""
import os

import pytest

# Defaults are set BEFORE importing app.* so config picks them up.
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-32-characters!!!!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("QUEUE_BACKEND", "inline")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("UPLOAD_DIR", "/tmp/nyx_test_uploads")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

import app.database as app_database
from app.database import Base, get_db
from app.main import app

# In-memory SQLite needs StaticPool + shared connection so tables created in
# one session are visible to others. For file-based SQLite or Postgres this
# branch is skipped and a regular engine is used.
if TEST_DATABASE_URL == "sqlite:///:memory:":
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # app.database builds its own engine at import time from DATABASE_URL.
    # Two separate create_engine("sqlite:///:memory:") calls are two separate,
    # unconnected databases even with an identical URL -- StaticPool only
    # shares a connection within the engine that owns it. Any code that opens
    # its own session via app.database.SessionLocal() (background workers,
    # the inline queue) would silently hit an empty, tableless database.
    # Point app.database at this fixture's engine so a session opened from
    # anywhere in the app during a test lands on the same in-memory DB.
    app_database.engine = engine
    app_database.SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
else:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def _import_models():
    # Importing the package registers every model on Base.metadata.
    import app.models  # noqa: F401
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate-limit state is process-global; reset it so login-heavy tests don't
    bleed counts into each other and trip the limiter."""
    from app.core.limiter import limiter

    limiter.reset()
    yield


@pytest.fixture()
def db(_import_models):
    """Per-test database. Tables are created and dropped each test so an
    in-memory SQLite with StaticPool stays isolated between tests."""
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email="admin@nyxapp.com",
        full_name="Test Admin",
        hashed_password=hash_password("Admin1234"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def admin_token(client, admin_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nyxapp.com", "password": "Admin1234"},
    )
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
