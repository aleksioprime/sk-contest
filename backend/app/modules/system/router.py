from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine

router = APIRouter(tags=['system'])


@router.get('/health', summary='Приложение запущено')
async def health() -> dict:
    return {'status': 'ok'}


@router.get('/health/ready', summary='Приложение готово: доступны БД и Redis')
async def ready(response: Response) -> dict:
    checks = {'database': await _check_database(), 'redis': await _check_redis()}
    ok = all(checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {'status': 'ok' if ok else 'unavailable', 'checks': checks}


@router.get('/v1/meta', summary='Версия и окружение')
async def meta() -> dict:
    return {
        'name': settings.project_name,
        'version': settings.version,
        'environment': settings.environment,
        'sites_base_domain': settings.sites_base_domain,
    }


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text('select 1'))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    client = Redis.from_url(settings.redis.dsn)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
