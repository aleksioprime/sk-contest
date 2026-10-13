"""Запуск синхронизации справочников со SkolStream (вызывается из воркера)."""

import logging

from sqlalchemy import select

from app.core.security import now_utc
from app.core.uow import UnitOfWork
from app.modules.audit.service import record
from app.modules.people.models import SyncRun
from app.modules.people.service import apply_directory
from app.modules.people.skolstream import SkolstreamClient

logger = logging.getLogger('sk_events.sync')


async def run_directory_sync(client: SkolstreamClient, run_id: int, uow_factory=UnitOfWork) -> dict:
    async with uow_factory() as uow:
        run = await uow.session.get(SyncRun, run_id)
        full = run.mode == 'full'
        last_success = None
        if not full:
            last_success = await uow.session.scalar(
                select(SyncRun.started_at)
                .where(SyncRun.status == 'success', SyncRun.id != run_id)
                .order_by(SyncRun.started_at.desc())
                .limit(1)
            )

    try:
        payload = await client.fetch_directory(last_success.isoformat() if last_success else None)
        async with uow_factory() as uow:
            stats = await apply_directory(uow.session, payload, full=full or last_success is None)
            run = await uow.session.get(SyncRun, run_id)
            run.status, run.stats, run.finished_at = 'success', stats, now_utc()
            record(uow.session, 'people.sync', 'sync_run', run_id, run.triggered_by_id, **stats)
        logger.info('Синхронизация %s завершена: %s', run_id, stats)
        return stats
    except Exception as exc:
        logger.exception('Синхронизация %s не удалась', run_id)
        async with uow_factory() as uow:
            run = await uow.session.get(SyncRun, run_id)
            run.status, run.error, run.finished_at = 'failed', str(exc)[:2000], now_utc()
        raise
