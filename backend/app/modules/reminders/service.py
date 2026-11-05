"""Напоминания по расписанию: незаконченные заявки перед закрытием приёма, судьи перед дедлайном листа.

Задачи запускаются воркером раз в час. Каждое напоминание уходит один раз: отметка reminded_at.
"""

import logging
from datetime import datetime, timedelta
from html import escape

from sk_common.audit import record
from sk_common.queue import Queue
from sk_common.security import now_utc
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.letters import app_link, button, can_email, moscow_time
from app.modules.applications.models import DRAFT, NEEDS_CHANGES, Application
from app.modules.evaluation.models import Evaluation, Sheet, SheetWork
from app.modules.events.models import Event

logger = logging.getLogger('sk_contest.reminders')

DRAFT_REMIND_BEFORE = timedelta(hours=48)
JUDGE_REMIND_BEFORE = timedelta(hours=24)


async def remind_drafts(session: AsyncSession, queue: Queue, now: datetime | None = None) -> int:
    """Заявки в черновике или на доработке, когда до конца заполнения меньше двух суток."""
    now = now or now_utc()
    deadline_at = func.coalesce(Event.details_closes_at, Event.registration_closes_at)
    apps = (
        await session.scalars(
            select(Application)
            .join(Event, Event.id == Application.event_id)
            .where(
                Application.status.in_((DRAFT, NEEDS_CHANGES)),
                Application.reminded_at.is_(None),
                Event.status.in_(('registration', 'running')),
                deadline_at > now,
                deadline_at <= now + DRAFT_REMIND_BEFORE,
            )
        )
    ).unique()
    sent = 0
    for app in apps:
        app.reminded_at = now
        if not can_email(app.user.email):
            continue
        event = app.event
        link = app_link(f'/my/applications/{app.id}')
        state = 'не отправлена' if app.status == DRAFT else 'ждёт правок'
        deadline = moscow_time(event.details_closes_at or event.registration_closes_at)
        text = (
            'Здравствуйте!\n\n'
            f'Ваша заявка №{app.number} на «{event.title}» {state}.\n'
            f'Заполнение заявок заканчивается {deadline}. После этого отправить её будет нельзя.\n\n'
            f'Открыть заявку: {link}'
        )
        html = (
            f'<p>Здравствуйте!</p><p>Ваша заявка №{app.number} на «{escape(event.title)}» {state}.</p>'
            f'<p>Заполнение заявок заканчивается <b>{deadline}</b>. После этого отправить её будет нельзя.</p>'
            + button(link, 'Открыть заявку')
        )
        await queue.enqueue('send_email', app.user.email, f'Заявка не отправлена: {event.title}', text, html)
        sent += 1
    await session.flush()
    return sent


async def _unfinished(session: AsyncSession, sheet_id: int) -> dict[int, int]:
    """Сколько работ каждый судья листа ещё не оценил."""
    rows = await session.execute(
        select(Evaluation.judge_id, Evaluation.id)
        .join(SheetWork, SheetWork.id == Evaluation.sheet_work_id)
        .where(SheetWork.sheet_id == sheet_id, Evaluation.is_anonymous.is_(False), Evaluation.is_scored.is_(False))
    )
    result: dict[int, int] = {}
    for judge_id, _ in rows:
        result[judge_id] = result.get(judge_id, 0) + 1
    return result


async def remind_sheet_judges(
    session: AsyncSession, queue: Queue, sheet: Sheet, *, only_new: bool = False, now: datetime | None = None
) -> tuple[int, int]:
    """Письма судьям листа, у которых остались неоценённые работы. Возвращает (отправлено, без email)."""
    now = now or now_utc()
    left = await _unfinished(session, sheet.id)
    event = await session.get(Event, sheet.event_id)
    sent = no_email = 0
    for judge in sheet.judges:
        count = left.get(judge.user_id, 0)
        if not count or (only_new and judge.reminded_at):
            continue
        judge.reminded_at = now
        if not can_email(judge.user.email):
            no_email += 1
            continue
        link = app_link(f'/judging/sheets/{sheet.id}')
        deadline = f' до {moscow_time(sheet.deadline)}' if sheet.deadline else ''
        text = (
            'Здравствуйте!\n\n'
            f'В листе «{sheet.title}» ({event.title}) осталось оценить работ: {count}.\n'
            f'Пожалуйста, завершите оценку{deadline}.\n\n'
            f'Открыть лист: {link}'
        )
        html = (
            f'<p>Здравствуйте!</p><p>В листе «{escape(sheet.title)}» ({escape(event.title)}) '
            f'осталось оценить работ: <b>{count}</b>.</p><p>Пожалуйста, завершите оценку{deadline}.</p>'
            + button(link, 'Открыть лист')
        )
        await queue.enqueue('send_email', judge.user.email, f'Оценка работ: {sheet.title}', text, html)
        sent += 1
    await session.flush()
    return sent, no_email


async def remind_judges(session: AsyncSession, queue: Queue, now: datetime | None = None) -> int:
    """Автоматически: за сутки до дедлайна активного листа, по одному письму каждому судье."""
    now = now or now_utc()
    sheets = await session.scalars(
        select(Sheet).where(Sheet.status == 'active', Sheet.deadline > now, Sheet.deadline <= now + JUDGE_REMIND_BEFORE)
    )
    total = 0
    for sheet in sheets.unique().all():
        sent, _ = await remind_sheet_judges(session, queue, sheet, only_new=True, now=now)
        total += sent
    return total


async def close_overdue_sheets(session: AsyncSession, now: datetime | None = None) -> int:
    """Активные листы с прошедшим дедлайном закрываются. Опоздавшим судьям модератор открывает доступ."""
    now = now or now_utc()
    overdue = select(Sheet).where(Sheet.status == 'active', Sheet.deadline <= now)
    sheets = (await session.scalars(overdue)).unique().all()
    for sheet in sheets:
        record(session, 'sheet.status', 'sheet', sheet.id, None, old=sheet.status, new='closed', reason='deadline')
        sheet.status = 'closed'
        for judge in sheet.judges:
            judge.reopened = False
    await session.flush()
    return len(sheets)


async def run_hourly(session: AsyncSession, queue: Queue) -> dict[str, int]:
    """Запускает почасовые напоминания и закрытие просроченных листов; возвращает число обработанных по видам."""
    now = now_utc()
    result = {
        'drafts': await remind_drafts(session, queue, now),
        'judges': await remind_judges(session, queue, now),
        'closed_sheets': await close_overdue_sheets(session, now),
    }
    if any(result.values()):
        logger.info('Напоминания: %s', result)
    return result
