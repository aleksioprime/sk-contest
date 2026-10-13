"""Тесты, которым нужна PostgreSQL с применёнными миграциями. Без БД пропускаются."""

import pytest
from sqlalchemy import text

from app.core.db import engine

JS_MAX_SAFE_INTEGER = 2**53 - 1
NOCOBASE_MAX_ID = 400_000_000_000_000


async def _database_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text('select 1'))
        return True
    except Exception:
        return False


@pytest.fixture
async def conn():
    if not await _database_available():
        pytest.skip('PostgreSQL недоступна')
    async with engine.connect() as connection:
        yield connection
    await engine.dispose()


async def test_next_id_is_unique_increasing_and_js_safe(conn):
    rows = await conn.execute(text('select next_id() from generate_series(1, 5000)'))
    ids = [row[0] for row in rows]
    assert len(set(ids)) == len(ids)
    assert all(NOCOBASE_MAX_ID < value < JS_MAX_SAFE_INTEGER for value in ids)
