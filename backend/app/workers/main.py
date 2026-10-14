"""Фоновые задачи на arq: письма, синхронизация SkolStream, позже PDF и выпуск доменов."""

import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.mail import send_mail
from app.core.queue import get_queue
from app.core.uow import UnitOfWork
from app.modules.people.models import SyncRun
from app.modules.people.skolstream import get_skolstream_client
from app.modules.people.sync import run_directory_sync
from app.modules.reminders.service import run_hourly

logger = logging.getLogger('sk_events.worker')


async def send_email(ctx: dict, to: str, subject: str, text: str, html: str | None = None) -> None:
    await send_mail(to, subject, text, html)
    logger.info('Письмо «%s» отправлено на %s', subject, to)


async def sync_directory(ctx: dict, run_id: int) -> dict:
    return await run_directory_sync(get_skolstream_client(), run_id)


async def nightly_sync(ctx: dict) -> None:
    if not settings.skolstream.directory_token:
        return
    async with UnitOfWork() as uow:
        if await uow.session.scalar(select(SyncRun.id).where(SyncRun.status == 'running').limit(1)):
            return
        run = SyncRun(mode='incremental')
        uow.session.add(run)
        await uow.session.flush()
        run_id = run.id
    await run_directory_sync(get_skolstream_client(), run_id)


async def hourly_reminders(ctx: dict) -> dict:
    """Напоминания о черновиках и дедлайнах листов, закрытие просроченных листов."""
    async with UnitOfWork() as uow:
        return await run_hourly(uow.session, get_queue())


async def startup(ctx: dict) -> None:
    setup_logging()
    logger.info('Воркер запущен, окружение %s', settings.environment)


class WorkerSettings:
    functions = [send_email, sync_directory]
    cron_jobs = [cron(nightly_sync, hour={3}, minute={0}), cron(hourly_reminders, minute={5})]
    on_startup = startup
    max_tries = 3
    redis_settings = RedisSettings(host=settings.redis.host, port=settings.redis.port, database=settings.redis.db)
