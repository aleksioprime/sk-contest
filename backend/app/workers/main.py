"""Фоновые задачи на arq: письма, синхронизация SkolStream, позже PDF и выпуск доменов."""

import logging

from arq import cron
from sk_common import worker
from sk_common.queue import get_queue
from sk_common.uow import UnitOfWork
from sk_common.web import setup_logging

from app.core.config import settings
from app.modules.reminders.service import run_hourly
from app.modules.sites.domains import get_dns_checker
from app.modules.sites.service import recheck_pending_domains

logger = logging.getLogger('sk_contest.worker')


async def hourly_reminders(ctx: dict) -> dict:
    """Напоминания о черновиках и дедлайнах листов, закрытие просроченных листов."""
    async with UnitOfWork() as uow:
        return await run_hourly(uow.session, get_queue())


async def check_domains(ctx: dict) -> int:
    """Свои домены лендингов, которые ещё ждут настройки DNS."""
    async with UnitOfWork() as uow:
        return await recheck_pending_domains(uow.session, get_dns_checker())


async def startup(ctx: dict) -> None:
    setup_logging()
    logger.info('Воркер запущен, окружение %s', settings.environment)


class WorkerSettings:
    functions = worker.FUNCTIONS
    cron_jobs = [
        *worker.CRON_JOBS,
        cron(hourly_reminders, minute={5}),
        cron(check_domains, minute=set(range(0, 60, 10))),
    ]
    on_startup = startup
    max_tries = 3
    redis_settings = worker.redis_settings()
