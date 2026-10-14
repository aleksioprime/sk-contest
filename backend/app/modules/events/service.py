from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.modules.applications.form import default_form
from app.modules.audit.service import record
from app.modules.events.models import Direction, Event, EventMember, ParticipationForm, Stage
from app.modules.events.templates import EVENT_TYPES, TRANSITIONS
from app.modules.files.models import StoredFile
from app.modules.people.models import User


class EventError(Exception):
    pass


async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    # populate_existing перечитывает связи, если объект уже был в сессии (например, сразу после создания)
    return await session.get(Event, event_id, populate_existing=True)


async def get_by_slug(session: AsyncSession, slug: str) -> Event | None:
    return await session.scalar(select(Event).where(Event.slug == slug))


async def slug_taken(session: AsyncSession, slug: str, exclude_id: int | None = None) -> bool:
    query = select(func.count()).select_from(Event).where(Event.slug == slug)
    if exclude_id:
        query = query.where(Event.id != exclude_id)
    return bool(await session.scalar(query))


async def list_events(session: AsyncSession, user: User, scope: str = 'mine') -> list[Event]:
    query = select(Event).order_by(Event.date_start.desc().nulls_first(), Event.created_at.desc())
    if not (scope == 'all' and user.is_superuser):
        query = query.where(Event.id.in_(select(EventMember.event_id).where(EventMember.user_id == user.id)))
    return list((await session.scalars(query)).unique())


async def create_event(
    session: AsyncSession, user: User, type_: str, title: str, slug: str, copy_from: Event | None = None
) -> Event:
    template = EVENT_TYPES.get(type_)
    if template is None:
        raise EventError('Неизвестный тип мероприятия')
    if await slug_taken(session, slug):
        raise EventError('Этот адрес уже занят')

    event = Event(
        type=type_,
        title=title,
        slug=slug,
        created_by_id=user.id,
        modules=dict(template['modules']),
        application_form=default_form(type_),
    )
    if copy_from is not None:
        event.copied_from_id = copy_from.id
        for field in ('short_description', 'description', 'level', 'format', 'place', 'modules', 'application_form'):
            setattr(event, field, getattr(copy_from, field))
        event.directions = [
            Direction(title=d.title, description=d.description, order=d.order) for d in copy_from.directions
        ]
        event.stages = [
            Stage(title=s.title, kind=s.kind, description=s.description, order=s.order) for s in copy_from.stages
        ]
        event.participation_forms = [
            ParticipationForm(title=f.title, order=f.order) for f in copy_from.participation_forms
        ]
    else:
        event.directions = []
        event.stages = [Stage(title=title_, kind=kind, order=i) for i, (title_, kind) in enumerate(template['stages'])]
        event.participation_forms = [
            ParticipationForm(title=title_, order=i) for i, title_ in enumerate(template['participation_forms'])
        ]
    event.members = [EventMember(user_id=user.id, role='organizer')]
    session.add(event)
    await session.flush()
    record(session, 'event.create', 'event', event.id, user.id, type=type_, copied_from=copy_from and copy_from.id)
    return event


async def update_event(session: AsyncSession, user: User, event: Event, changes: dict) -> Event:
    if 'slug' in changes and await slug_taken(session, changes['slug'], exclude_id=event.id):
        raise EventError('Этот адрес уже занят')
    if changes.get('cover_file_id'):
        cover = await session.get(StoredFile, changes['cover_file_id'])
        if cover is None or not cover.is_public or not cover.content_type.startswith('image/'):
            raise EventError('Обложка должна быть загруженной картинкой')
    if 'modules' in changes:
        changes['modules'] = {**event.modules, **changes['modules']}
    for field, value in changes.items():
        setattr(event, field, value)
    _check_dates(event)
    record(session, 'event.update', 'event', event.id, user.id, fields=sorted(changes))
    await session.flush()
    return event


def _check_dates(event: Event) -> None:
    if event.date_start and event.date_end and event.date_end < event.date_start:
        raise EventError('Дата окончания раньше даты начала')
    opens, closes = event.registration_opens_at, event.registration_closes_at
    if opens and closes and closes <= opens:
        raise EventError('Приём заявок должен закрываться позже, чем открывается')


async def change_status(session: AsyncSession, user: User, event: Event, new_status: str) -> Event:
    if new_status not in TRANSITIONS[event.status]:
        raise EventError('Такой переход статуса недоступен')
    if new_status != 'draft' and not event.date_start:
        raise EventError('Перед публикацией укажите дату начала мероприятия')
    record(session, 'event.status', 'event', event.id, user.id, old=event.status, new=new_status)
    event.status = new_status
    await session.flush()
    return event


def public_event_payload(event: Event) -> dict:
    """Публичные данные мероприятия для лендинга (схема PublicEvent)."""
    from app.modules.events.schemas import PublicEvent

    fields = {c: getattr(event, c) for c in PublicEvent.model_fields if c not in ('registration_open', 'cover_url')}
    return {
        **fields,
        'registration_open': registration_open(event),
        'cover_url': f'/api/v1/public/files/{event.cover_file_id}' if event.cover_file_id else None,
    }


def registration_open(event: Event, at: datetime | None = None) -> bool:
    if event.status != 'registration' or not event.modules.get('registration'):
        return False
    at = at or now_utc()
    if event.registration_opens_at and at < event.registration_opens_at:
        return False
    return not (event.registration_closes_at and at > event.registration_closes_at)


# --- Направления, этапы, формы участия -----------------------------------------------------

CHILDREN = {'directions': Direction, 'stages': Stage, 'forms': ParticipationForm}
CHILD_ATTR = {'directions': 'directions', 'stages': 'stages', 'forms': 'participation_forms'}


async def add_child(session: AsyncSession, event: Event, kind: str, data: dict):
    items = getattr(event, CHILD_ATTR[kind])
    child = CHILDREN[kind](**data, order=max((item.order for item in items), default=-1) + 1)
    items.append(child)
    await session.flush()
    return child


def find_child(event: Event, kind: str, child_id: int):
    child = next((item for item in getattr(event, CHILD_ATTR[kind]) if item.id == child_id), None)
    if child is None:
        raise EventError('Элемент не найден')
    return child


async def reorder_children(session: AsyncSession, event: Event, kind: str, ids: list[int]) -> None:
    items = {item.id: item for item in getattr(event, CHILD_ATTR[kind])}
    if set(ids) != set(items):
        raise EventError('Передайте все элементы списка')
    for order, item_id in enumerate(ids):
        items[item_id].order = order
    getattr(event, CHILD_ATTR[kind]).sort(key=lambda item: item.order)
    await session.flush()


# --- Команда ---------------------------------------------------------------------------------


async def add_member(session: AsyncSession, actor: User, event: Event, user: User, role: str) -> EventMember:
    existing = next((m for m in event.members if m.user_id == user.id and m.role == role), None)
    if existing:
        return existing
    member = EventMember(user_id=user.id, role=role)
    event.members.append(member)
    await session.flush()
    await session.refresh(member, ['user'])
    record(session, 'event.member.add', 'event', event.id, actor.id, user_id=user.id, role=role)
    return member


async def remove_member(session: AsyncSession, actor: User, event: Event, member_id: int) -> None:
    member = next((m for m in event.members if m.id == member_id), None)
    if member is None:
        raise EventError('Участник команды не найден')
    organizers = [m for m in event.members if m.role == 'organizer']
    if member.role == 'organizer' and len(organizers) == 1:
        raise EventError('Нельзя удалить единственного организатора')
    event.members.remove(member)
    record(session, 'event.member.remove', 'event', event.id, actor.id, user_id=member.user_id, role=member.role)
    await session.flush()
