"""Shared pytest fixtures.

Environment variables are set BEFORE any ``app`` import so that settings,
engines and singletons bind to the throwaway test database.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

os.environ["SMARTSUPPORT_ENVIRONMENT"] = "test"
os.environ["SMARTSUPPORT_DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/smartsupport_test"
)
os.environ["SMARTSUPPORT_SYNC_DATABASE_URL"] = (
    "postgresql+psycopg2://postgres:mysecretpassword@localhost:5432/smartsupport_test"
)
os.environ["SMARTSUPPORT_JWT_SECRET"] = "test-secret-key"
os.environ["SMARTSUPPORT_UPLOAD_DIR"] = tempfile.mkdtemp(prefix="ss-uploads-")
os.environ["SMARTSUPPORT_CELERY_BROKER_URL"] = "memory://"
os.environ["SMARTSUPPORT_CELERY_RESULT_BACKEND"] = "cache+memory://"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fakeredis import FakeRedis as FakeSyncRedis  # noqa: E402
from fakeredis import aioredis as fakeredis_aio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core import cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db.base import Base  # noqa: E402
from app.db.session import SessionFactory, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.api.deps import get_db  # noqa: E402
import app.models  # noqa: F401,E402  (register tables)

ADMIN = {
    "email": "admin@test.io",
    "password": "SuperSecret1",
    "full_name": "Ada Admin",
}
MEMBER = {
    "email": "member@test.io",
    "password": "SuperSecret2",
    "full_name": "Milo Member",
}


@pytest.fixture()
def fake_redis() -> Iterator[None]:
    """Inject fakeredis clients (async + sync) into the cache module."""
    cache.init_redis(
        client=fakeredis_aio.FakeRedis(decode_responses=True),
        binary_client=fakeredis_aio.FakeRedis(decode_responses=False),
    )
    cache.init_sync_redis(client=FakeSyncRedis(decode_responses=False))
    yield
    cache.reset_redis()


@pytest.fixture(autouse=True)
def _stub_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never hit a real broker from tests."""
    from app.workers.tasks import ingest_document

    monkeypatch.setattr(ingest_document, "delay", lambda *a, **k: None, raising=False)


@pytest.fixture(autouse=True)
async def _tables() -> AsyncIterator[None]:
    """Fresh schema per test (fast enough on local PG, guarantees isolation)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)



@pytest.fixture()
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


@pytest.fixture()
def app():
    application = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as session:
            yield session

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_and_login(
    client: AsyncClient, data: dict[str, str]
) -> dict[str, str]:
    """Register + login; returns Authorization headers for the user."""
    response = await client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 201, response.text
    login = await client.post(
        "/api/v1/auth/login", json={"email": data["email"], "password": data["password"]}
    )
    assert login.status_code == 200, login.text
    return auth_headers(login.json()["access_token"])


@pytest.fixture()
async def admin_headers(client) -> dict[str, str]:
    """First registered user in a fresh DB is promoted to admin."""
    return await register_and_login(client, ADMIN)


@pytest.fixture()
async def member_headers(client, admin_headers) -> dict[str, str]:
    return await register_and_login(client, MEMBER)


@pytest.fixture()
def upload_dir() -> Path:
    return Path(os.environ["SMARTSUPPORT_UPLOAD_DIR"])
