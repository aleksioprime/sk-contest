"""Фоновые задачи на arq: письма, PDF, синхронизация SkolStream, выпуск доменов."""

import logging

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger('sk_events.worker')


async def ping(ctx: dict) -> str:
    logger.info('Задача ping выполнена')
    return 'pong'


async def startup(ctx: dict) -> None:
    setup_logging()
    logger.info('Воркер запущен, окружение %s', settings.environment)


class WorkerSettings:
    functions = [ping]
    on_startup = startup
    redis_settings = RedisSettings(host=settings.redis.host, port=settings.redis.port, database=settings.redis.db)
