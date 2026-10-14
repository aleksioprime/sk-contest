from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, Db
from app.core.redis import get_redis
from app.modules.audit.service import record
from app.modules.events.models import Event
from app.modules.events.permissions import ensure_manage, ensure_view
from app.modules.events.service import get_by_slug, get_event
from app.modules.people.models import User
from app.modules.sites import domains as domain_service
from app.modules.sites import service
from app.modules.sites.content import ContentError
from app.modules.sites.models import Site, SiteDomain, SiteVersion
from app.modules.sites.schemas import DomainIn, DomainOut, DraftIn, PublishIn, SiteOut, VersionOut

router = APIRouter(prefix='/v1', tags=['sites'])
public_router = APIRouter(prefix='/v1/public/sites', tags=['public'])


def _not_found(what: str = 'Сайт не найден') -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, what)


def _bad(exc: Exception | str) -> HTTPException:
    if isinstance(exc, ContentError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, {'message': 'Сайт не сохранён: ошибки в блоках', 'errors': exc.errors}
        )
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _event(db, event_id: int, user: User) -> Event:
    event = await get_event(db, event_id)
    if event is None:
        raise _not_found('Мероприятие не найдено')
    ensure_view(user, event)
    ensure_manage(user, event)
    return event


async def _site(db, event_id: int, user: User) -> tuple[Event, Site]:
    event = await _event(db, event_id, user)
    site = await service.get_site(db, event.id)
    if site is None:
        raise _not_found('Сайт ещё не создан')
    return event, site


def _domain_out(domain: SiteDomain) -> DomainOut:
    return DomainOut(
        id=domain.id,
        domain=domain.domain,
        status=domain.status,
        error=domain.error,
        checked_at=domain.checked_at,
        verified_at=domain.verified_at,
        url=f'https://{domain.domain}',
    )


async def _site_out(db, event: Event, site: Site | None) -> SiteOut:
    base = settings.sites_base_domain
    urls = [f'https://{event.slug}.{base}', f'https://{base}/{event.slug}']
    if site is None:
        return SiteOut(
            exists=False,
            draft=None,
            updated_at=None,
            published_at=None,
            published_version=None,
            has_unpublished_changes=False,
            urls=urls,
            cname_target=settings.sites_cname_target,
            domains=[],
        )
    published = await db.get(SiteVersion, site.published_version_id) if site.published_version_id else None
    return SiteOut(
        exists=True,
        draft=site.draft,
        updated_at=site.updated_at,
        published_at=site.published_at,
        published_version=published.number if published else None,
        has_unpublished_changes=published is None or published.content != site.draft,
        urls=[*(f'https://{d.domain}' for d in site.domains if d.status == 'active'), *urls],
        cname_target=settings.sites_cname_target,
        domains=[_domain_out(d) for d in site.domains],
    )


@router.get('/events/{event_id}/site', response_model=SiteOut, summary='Сайт мероприятия: черновик и публикация')
async def get_site(event_id: int, db: Db, user: CurrentUser):
    event = await _event(db, event_id, user)
    return await _site_out(db, event, await service.get_site(db, event.id))


@router.put('/events/{event_id}/site', response_model=SiteOut, summary='Сохранить черновик сайта')
async def save_draft(event_id: int, payload: DraftIn, db: Db, user: CurrentUser):
    event = await _event(db, event_id, user)
    try:
        await service.save_draft(db, user, event, payload.content)
    except (ContentError, service.SiteError) as exc:
        raise _bad(exc) from exc
    await db.commit()
    return await _site_out(db, event, await service.get_site(db, event.id))


@router.get('/events/{event_id}/site/data', summary='Данные мероприятия для превью в конструкторе')
async def preview_data(event_id: int, db: Db, user: CurrentUser) -> dict:
    event = await _event(db, event_id, user)
    return await service.site_data(db, event)


@router.post('/events/{event_id}/site/publish', response_model=SiteOut, summary='Опубликовать черновик')
async def publish(event_id: int, payload: PublishIn, db: Db, user: CurrentUser):
    event, site = await _site(db, event_id, user)
    await service.publish(db, user, site, payload.note)
    await db.commit()
    await service.invalidate(get_redis(), event, site.domains)
    return await _site_out(db, event, await service.get_site(db, event.id))


@router.post('/events/{event_id}/site/unpublish', response_model=SiteOut, summary='Снять сайт с публикации')
async def unpublish(event_id: int, db: Db, user: CurrentUser):
    event, site = await _site(db, event_id, user)
    await service.unpublish(db, user, site)
    await db.commit()
    await service.invalidate(get_redis(), event, site.domains)
    return await _site_out(db, event, await service.get_site(db, event.id))


@router.get('/events/{event_id}/site/versions', response_model=list[VersionOut], summary='История публикаций')
async def versions(event_id: int, db: Db, user: CurrentUser):
    _, site = await _site(db, event_id, user)
    result = []
    for version in await service.versions(db, site):
        author = await db.get(User, version.created_by_id) if version.created_by_id else None
        result.append(
            VersionOut(
                id=version.id,
                number=version.number,
                note=version.note,
                created_at=version.created_at,
                created_by=(author.person.full_name if author and author.person else author.email if author else None),
                published=version.id == site.published_version_id,
            )
        )
    return result


@router.post(
    '/events/{event_id}/site/versions/{version_id}/restore', response_model=SiteOut, summary='Вернуть черновик к версии'
)
async def restore(event_id: int, version_id: int, db: Db, user: CurrentUser):
    event, site = await _site(db, event_id, user)
    version = await db.get(SiteVersion, version_id)
    if version is None or version.site_id != site.id:
        raise _not_found('Версия не найдена')
    await service.restore(db, user, site, version)
    await db.commit()
    return await _site_out(db, event, await service.get_site(db, event.id))


# --- Свои домены ---------------------------------------------------------------------------------


@router.post('/events/{event_id}/site/domains', response_model=SiteOut, status_code=201, summary='Добавить свой домен')
async def add_domain(
    event_id: int,
    payload: DomainIn,
    db: Db,
    user: CurrentUser,
    checker: Annotated[domain_service.DnsChecker, Depends(domain_service.get_dns_checker)],
):
    event, site = await _site(db, event_id, user)
    try:
        name = domain_service.normalize_domain(payload.domain)
    except domain_service.DomainError as exc:
        raise _bad(exc) from exc
    if await db.scalar(select(SiteDomain.id).where(SiteDomain.domain == name)):
        raise _bad('Этот домен уже подключён к другому сайту')
    if len(site.domains) >= 3:
        raise _bad('К сайту можно подключить не больше трёх доменов')
    domain = SiteDomain(site_id=site.id, domain=name)
    db.add(domain)
    await db.flush()
    record(db, 'site.domain_add', 'site', site.id, user.id, domain=name)
    await service.verify_domain(db, domain, checker)
    await db.commit()
    return await _site_out(db, event, await service.get_site(db, event.id))


async def _domain(db, domain_id: int, user: User) -> tuple[Event, Site, SiteDomain]:
    domain = await db.get(SiteDomain, domain_id)
    if domain is None:
        raise _not_found('Домен не найден')
    site = await db.get(Site, domain.site_id)
    event, site = await _site(db, site.event_id, user)
    return event, site, domain


@router.post('/site-domains/{domain_id}/check', response_model=SiteOut, summary='Проверить DNS домена')
async def check_domain(
    domain_id: int,
    db: Db,
    user: CurrentUser,
    checker: Annotated[domain_service.DnsChecker, Depends(domain_service.get_dns_checker)],
):
    event, site, domain = await _domain(db, domain_id, user)
    await service.verify_domain(db, domain, checker)
    await db.commit()
    await service.invalidate(get_redis(), event, [domain])
    return await _site_out(db, event, await service.get_site(db, event.id))


@router.delete('/site-domains/{domain_id}', response_model=SiteOut, summary='Отключить домен')
async def delete_domain(domain_id: int, db: Db, user: CurrentUser):
    event, site, domain = await _domain(db, domain_id, user)
    domain_service.remove_route(domain.domain)
    record(db, 'site.domain_delete', 'site', site.id, user.id, domain=domain.domain)
    await db.delete(domain)
    await db.commit()
    await service.invalidate(get_redis(), event, [domain])
    return await _site_out(db, event, await service.get_site(db, event.id))


# --- Публичные данные для сервиса sites ----------------------------------------------------------


async def _public(db, event: Event | None, key: str) -> dict:
    if event is None or event.status == 'draft':
        raise _not_found()
    payload = await service.public_site(db, event)
    await service.store(get_redis(), key, payload)
    return payload


@public_router.get('/by-slug/{slug}', summary='Лендинг по адресу мероприятия')
async def by_slug(slug: str, db: Db) -> dict:
    key = service.cache_key('slug', slug)
    if hit := await service.cached(get_redis(), key):
        return hit
    return await _public(db, await get_by_slug(db, slug), key)


@public_router.get('/by-domain/{domain}', summary='Лендинг по своему домену')
async def by_domain(domain: str, db: Db) -> dict:
    name = domain.lower().rstrip('.')
    key = service.cache_key('domain', name)
    if hit := await service.cached(get_redis(), key):
        return hit
    row = await db.scalar(select(SiteDomain).where(SiteDomain.domain == name, SiteDomain.status == 'active'))
    if row is None:
        raise _not_found()
    site = await db.get(Site, row.site_id)
    return await _public(db, await get_event(db, site.event_id), key)
