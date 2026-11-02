"""Фоновые задачи на arq: письма, синхронизация SkolStream, позже PDF и выпуск доменов."""

import logging

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.mail import send_mail
from app.core.queue import get_queue
from app.core.uow import UnitOfWork
from app.modules.people.skolstream import get_skolstream_client
from app.modules.people.sync import run_directory_sync, start_scheduled_sync
from app.modules.reminders.service import run_hourly
from app.modules.sites.domains import get_dns_checker
from app.modules.sites.service import recheck_pending_domains

logger = logging.getLogger('sk_contest.worker')


async def send_email(ctx: dict, to: str, subject: str, text: str, html: str | None = None) -> None:
    await send_mail(to, subject, text, html)
    logger.info('Письмо «%s» отправлено на %s', subject, to)


async def sync_directory(ctx: dict, run_id: int) -> dict:
    return await run_directory_sync(get_skolstream_client(), run_id)


async def frequent_sync(ctx: dict) -> None:
    """Изменения справочника SkolStream каждые 10 минут: новый ученик виден почти сразу."""
    await start_scheduled_sync(get_skolstream_client(), 'incremental')


async def nightly_sync(ctx: dict) -> None:
    """Полный срез ночью: отключает тех, кого нет в SkolStream, и чистит журнал запусков."""
    await start_scheduled_sync(get_skolstream_client(), 'full')


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
    functions = [send_email, sync_directory]
    cron_jobs = [
        cron(nightly_sync, hour={3}, minute={0}),
        cron(frequent_sync, minute=set(range(2, 60, 10))),
        cron(hourly_reminders, minute={5}),
        cron(check_domains, minute=set(range(0, 60, 10))),
    ]
    on_startup = startup
    max_tries = 3
    redis_settings = RedisSettings(host=settings.redis.host, port=settings.redis.port, database=settings.redis.db)
