"""Общие фикстуры. Тесты с БД работают на отдельной базе sk_events_test и пропускаются, если PostgreSQL недоступна."""

import os

os.environ.setdefault('DB__NAME', 'sk_events_test')
os.environ['DB__NULL_POOL'] = 'true'
os.environ['REDIS__DB'] = '1'  # тесты очищают Redis, dev-очередь в базе 0 не трогаем
os.environ.setdefault('ENVIRONMENT', 'local')

import asyncio  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from pathlib import Path  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import redis as redis_module  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import session_maker  # noqa: E402
from app.core.queue import get_queue  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.people.skolstream import get_skolstream_client  # noqa: E402
from tests.fakes import FakeQueue, FakeSkolstream  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
ORIGIN = 'http://localhost:8501'


async def _create_database() -> bool:
    db = settings.db
    try:
        conn = await asyncpg.connect(
            host=db.host, port=db.port, user=db.user, password=db.password, database='postgres', timeout=3
        )
    except (OSError, asyncpg.PostgresError):
        return False
    try:
        exists = await conn.fetchval('select 1 from pg_database where datname = $1', db.name)
        if not exists:
            await conn.execute(f'create database "{db.name}"')
    finally:
        await conn.close()
    return True


@pytest.fixture(scope='session')
def database_ready() -> bool:
    if not asyncio.run(_create_database()):
        return False
    subprocess.run(
        [sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=BACKEND_DIR, check=True, env=os.environ.copy()
    )
    return True


@pytest.fixture
async def db(database_ready):
    """Чистая БД для теста."""
    if not database_ready:
        pytest.skip('PostgreSQL недоступна')
    async with session_maker() as session:
        tables = await session.scalars(
            text("select tablename from pg_tables where schemaname = 'public' and tablename != 'alembic_version'")
        )
        names = ', '.join(f'"{name}"' for name in tables)
        if names:
            await session.execute(text(f'truncate {names} restart identity cascade'))
        await session.commit()
        yield session


@pytest.fixture
async def redis_clean(database_ready):
    redis_module._client = None
    client = redis_module.get_redis()
    try:
        await client.flushdb()
    except Exception:
        pytest.skip('Redis недоступен')
    yield client
    await client.aclose()
    redis_module._client = None


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def skolstream() -> FakeSkolstream:
    return FakeSkolstream()


@pytest.fixture
async def client(queue, skolstream) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_skolstream_client] = lambda: skolstream
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=ORIGIN, headers={'Origin': ORIGIN}) as http:
        yield http
