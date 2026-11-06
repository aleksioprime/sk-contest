"""Фоновые задачи на arq: письма, синхронизация SkolStream, напоминания."""

import logging
from dataclasses import replace

from arq import cron
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sk_common import worker
from sk_common.queue import get_queue
from sk_common.uow import UnitOfWork
from sk_common.web import setup_logging

from app.core.config import settings
from app.modules.reminders.service import run_hourly

logger = logging.getLogger('sk_contest.worker')


async def hourly_reminders(ctx: dict) -> dict:
    """Напоминания о черновиках и дедлайнах листов, закрытие просроченных листов."""
    async with UnitOfWork() as uow:
        return await run_hourly(uow.session, get_queue())


async def startup(ctx: dict) -> None:
    """Настраивает логирование при запуске воркера."""
    setup_logging()
    logger.info('Воркер запущен, окружение %s', settings.environment)


class WorkerSettings:
    """Настройки воркера arq: задачи, расписание (напоминания каждый час в :05), повторы и Redis."""

    functions = worker.FUNCTIONS
    cron_jobs = [
        *worker.CRON_JOBS,
        cron(hourly_reminders, minute={5}),
    ]
    on_startup = startup
    max_tries = 3
    # При выкатке соединение с Redis может оборваться; без повторов воркер падает на первом же сбое
    redis_settings = replace(
        worker.redis_settings(),
        retry=Retry(ExponentialBackoff(cap=5, base=0.5), 10),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    )
