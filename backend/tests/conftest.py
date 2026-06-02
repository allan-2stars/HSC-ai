"""
Test configuration.

Strategy:
  - Uses a separate hscai_test PostgreSQL database.
  - Tables are created once per test session and truncated between tests.
  - asyncio.run() is used in sync fixtures (asyncio_mode = strict means no
    auto-async fixture promotion, so each asyncio.run() gets a clean loop).
  - NullPool prevents asyncpg connection sharing across event-loop boundaries.
  - TestClient (sync) bridges to the async FastAPI app via anyio internally.
"""
import asyncio
import os
from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

# Override Docker-internal URLs with host-side addresses before any app imports.
# pydantic-settings gives env vars priority over .env files, so these take effect
# even though .env contains the Docker-internal values.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://hscai:change_me_in_production@localhost:5435/hscai")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models as _app_models  # noqa: F401 — registers all ORM models with Base.metadata
from app.core.database import get_db
from app.main import app
from app.models.base import Base

# Replace the app engine with NullPool so each asyncio.run() in fixtures gets fresh
# connections instead of hitting pool connections from closed event loops.
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool as _NullPool
from app.core import database as _db_module
_db_module.engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,
    poolclass=_NullPool,
)

# Read TEST_DATABASE_URL from environment; default to Docker-internal address.
# Inside Docker, .env provides: postgresql+asyncpg://...@postgres:5432/hscai_test
# On the host, set TEST_DATABASE_URL to localhost:5435 for local pytest runs.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://hscai:change_me_in_production@postgres:5432/hscai_test",
)

# Build admin URL (to the default 'hscai' database) by replacing only the path.
_parsed = urlparse(TEST_DATABASE_URL)
_admin_parsed = _parsed._replace(path="/hscai")
ADMIN_DATABASE_URL = urlunparse(_admin_parsed)

_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_SessionFactory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _run(coro):
    return asyncio.run(coro)


# ── schema lifecycle ──────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def db_schema() -> Generator:
    """Create all tables once at session start; drop on exit."""
    async def _create():
        # Ensure hscai_test database exists
        admin_engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
        async with admin_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname='hscai_test'")
            )
            if not result.fetchone():
                await conn.execute(text("CREATE DATABASE hscai_test"))
        await admin_engine.dispose()

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _engine.dispose()

    _run(_create())
    yield
    _run(_drop())


@pytest.fixture
def clean_tables(db_schema) -> Generator:
    """Truncate all tables between tests to isolate state."""
    yield

    async def _clean():
        table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if table_names:
            async with _engine.begin() as conn:
                # TRUNCATE with CASCADE handles circular FKs (e.g. questions ↔ question_versions)
                await conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))

    _run(_clean())


# ── test client ───────────────────────────────────────────────────

@pytest.fixture
def client(clean_tables) -> Generator:
    """Sync TestClient with DB pointed at hscai_test."""
    async def override_get_db():
        async with _SessionFactory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── helpers ───────────────────────────────────────────────────────

def register_parent(client: TestClient, email: str = "parent@test.com", password: str = "TestPass123", display_name: str = "Test Parent") -> dict:
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "display_name": display_name
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def create_admin_and_login(
    client: TestClient,
    email: str = "admin@test.com",
    password: str = "AdminPass123",
) -> dict:
    """Create an admin user directly in the test DB, then login to get tokens."""
    async def _seed():
        async with _SessionFactory() as session:
            from app.core.security import hash_password
            from app.models.user import AdminProfile, User, UserRole
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.admin,
            )
            session.add(user)
            await session.flush()
            profile = AdminProfile(user_id=user.id, display_name="Test Admin")
            session.add(profile)
            await session.commit()

    _run(_seed())
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()
