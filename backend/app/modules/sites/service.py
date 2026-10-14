"""Сайт мероприятия: черновик, публикация версий, откат и данные для лендинга."""

import json
import logging
from datetime import timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.modules.applications.models import ACCEPTED, NEEDS_CHANGES, SUBMITTED, Application, ApplicationMember
from app.modules.audit.service import record
from app.modules.events.models import Event
from app.modules.events.schemas import PublicEvent
from app.modules.events.service import public_event_payload
from app.modules.files.models import StoredFile
from app.modules.people.models import User
from app.modules.sites import domains as domain_service
from app.modules.sites.content import validate_content
from app.modules.sites.models import Site, SiteDomain, SiteVersion
from app.modules.stages.models import WITHDRAWN, DefenseSlot, StageParticipation
from app.modules.stages.service import published_winners

logger = logging.getLogger('sk_events.sites')

CACHE_TTL = 120
ACTIVE_APPLICATIONS = (SUBMITTED, NEEDS_CHANGES, ACCEPTED)


class SiteError(Exception):
    pass


async def get_site(session: AsyncSession, event_id: int) -> Site | None:
    return await session.scalar(select(Site).where(Site.event_id == event_id).execution_options(populate_existing=True))


async def _check_files(session: AsyncSession, file_ids: set[int]) -> None:
    if not file_ids:
        return
    public = set(
        await session.scalars(select(StoredFile.id).where(StoredFile.id.in_(file_ids), StoredFile.is_public.is_(True)))
    )
    if missing := file_ids - public:
        raise SiteError(f'Файлы не найдены или не опубликованы: {", ".join(map(str, sorted(missing)))}')


async def save_draft(session: AsyncSession, actor: User, event: Event, raw: dict) -> Site:
    content, files = validate_content(raw)
    await _check_files(session, files)
    site = await get_site(session, event.id)
    if site is None:
        site = Site(event_id=event.id, draft=content, domains=[])
        session.add(site)
        record(session, 'site.create', 'event', event.id, actor.id)
    else:
        site.draft = content
    await session.flush()
    return site


async def publish(session: AsyncSession, actor: User, site: Site, note: str = '') -> SiteVersion:
    number = (await session.scalar(select(func.max(SiteVersion.number)).where(SiteVersion.site_id == site.id))) or 0
    version = SiteVersion(
        site_id=site.id,
        number=number + 1,
        content=site.draft,
        note=note[:200],
        created_by_id=actor.id,
        created_at=now_utc(),
    )
    session.add(version)
    await session.flush()
    site.published_version_id = version.id
    site.published_at = version.created_at
    record(session, 'site.publish', 'site', site.id, actor.id, version=version.number)
    await session.flush()
    return version


async def unpublish(session: AsyncSession, actor: User, site: Site) -> None:
    site.published_version_id = None
    site.published_at = None
    record(session, 'site.unpublish', 'site', site.id, actor.id)
    await session.flush()


async def restore(session: AsyncSession, actor: User, site: Site, version: SiteVersion) -> None:
    """Вернуть черновик к версии. Опубликованная версия не меняется, пока черновик не опубликуют."""
    site.draft = version.content
    record(session, 'site.restore', 'site', site.id, actor.id, version=version.number)
    await session.flush()


async def versions(session: AsyncSession, site: Site) -> list[SiteVersion]:
    return list(
        await session.scalars(
            select(SiteVersion).where(SiteVersion.site_id == site.id).order_by(SiteVersion.number.desc())
        )
    )


async def published_content(session: AsyncSession, site: Site | None) -> dict | None:
    if site is None or site.published_version_id is None:
        return None
    return await session.scalar(select(SiteVersion.content).where(SiteVersion.id == site.published_version_id))


# --- Свои домены --------------------------------------------------------------------------------


async def verify_domain(session: AsyncSession, domain: SiteDomain, checker: domain_service.DnsChecker) -> None:
    """Проверить DNS. При первом успехе — записать маршрут в Traefik и включить домен."""
    problem = await checker.check(domain.domain)
    domain.checked_at = now_utc()
    if problem:
        domain.status = 'error' if domain.status == 'active' else 'pending'
        domain.error = problem
        return
    if domain.status != 'active':
        domain_service.write_route(domain.domain)
        domain.status = 'active'
        domain.verified_at = domain.checked_at
    domain.error = ''


async def recheck_pending_domains(session: AsyncSession, checker: domain_service.DnsChecker) -> int:
    """Воркер: DNS обновляется не сразу, поэтому ожидающие домены перепроверяются в течение недели."""
    since = now_utc() - timedelta(days=7)
    rows = await session.scalars(
        select(SiteDomain).where(SiteDomain.status == 'pending', SiteDomain.created_at >= since)
    )
    activated = 0
    for domain in rows.all():
        await verify_domain(session, domain, checker)
        activated += domain.status == 'active'
    await session.flush()
    return activated


# --- Данные мероприятия для блоков ---------------------------------------------------------------


async def program(session: AsyncSession, event: Event) -> list[dict]:
    """Слоты защит всех этапов с работами. Без имён участников: на лендинге только номер и название."""
    stages = {stage.id: stage.title for stage in event.stages}
    if not stages:
        return []
    slots = list(
        await session.scalars(
            select(DefenseSlot).where(DefenseSlot.stage_id.in_(stages)).order_by(DefenseSlot.starts_at, DefenseSlot.id)
        )
    )
    works: dict[int, list[dict]] = {}
    if slots:
        rows = await session.scalars(
            select(StageParticipation)
            .where(StageParticipation.slot_id.in_([s.id for s in slots]), StageParticipation.status != WITHDRAWN)
            .order_by(StageParticipation.slot_order, StageParticipation.id)
        )
        for row in rows.unique():
            works.setdefault(row.slot_id, []).append({'number': row.application.number, 'title': row.application.title})
    return [
        {
            'starts_at': slot.starts_at.isoformat(),
            'ends_at': slot.ends_at.isoformat() if slot.ends_at else None,
            'room': slot.room,
            'title': slot.title,
            'stage': stages[slot.stage_id] if len(stages) > 1 else '',
            'works': works.get(slot.id, []),
        }
        for slot in slots
    ]


async def stats(session: AsyncSession, event: Event) -> dict:
    applications = await session.scalar(
        select(func.count(Application.id)).where(
            Application.event_id == event.id, Application.status.in_(ACTIVE_APPLICATIONS)
        )
    )
    participants = await session.scalar(
        select(func.count(ApplicationMember.id))
        .join(Application, Application.id == ApplicationMember.application_id)
        .where(
            Application.event_id == event.id,
            Application.status.in_(ACTIVE_APPLICATIONS),
            ApplicationMember.role == 'participant',
        )
    )
    return {
        'applications': applications or 0,
        'participants': participants or 0,
        'directions': len(event.directions),
        'stages': len(event.stages),
    }


async def site_data(session: AsyncSession, event: Event) -> dict:
    return {
        'event': PublicEvent.model_validate(public_event_payload(event)).model_dump(mode='json'),
        'results': await published_winners(session, event),
        'program': await program(session, event),
        'stats': await stats(session, event),
    }


async def public_site(session: AsyncSession, event: Event) -> dict:
    """Всё, что нужно sites для рендера: опубликованное содержимое (или null — тогда шаблон) и данные."""
    site = await get_site(session, event.id)
    domain = next((d.domain for d in site.domains if d.status == 'active'), None) if site else None
    return {
        'content': await published_content(session, site),
        'domain': domain,
        **(await site_data(session, event)),
    }


# --- Кэш опубликованных сайтов ------------------------------------------------------------------


def cache_key(kind: str, value: str) -> str:
    return f'site:{kind}:{value}'


async def cached(redis: Redis, key: str) -> dict | None:
    try:
        raw = await redis.get(key)
    except Exception:  # кэш не обязателен: без Redis отдаём из БД
        logger.warning('Кэш сайтов недоступен')
        return None
    return json.loads(raw) if raw else None


async def store(redis: Redis, key: str, payload: dict) -> None:
    try:
        await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=CACHE_TTL)
    except Exception:
        logger.warning('Кэш сайтов недоступен')


async def invalidate(redis: Redis, event: Event, domains: list[SiteDomain] | None = None) -> None:
    keys = [cache_key('slug', event.slug), *(cache_key('domain', d.domain) for d in domains or [])]
    try:
        await redis.delete(*keys)
    except Exception:
        logger.warning('Кэш сайтов недоступен')
