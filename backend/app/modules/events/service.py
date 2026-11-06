"""Логика мероприятий: создание, изменение, статусы, вложенные списки и команда."""

from datetime import datetime

from sk_common.audit import record
from sk_common.people.models import User
from sk_common.security import now_utc
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.form import default_form
from app.modules.events.models import Direction, Event, EventMember, ParticipationForm, Stage
from app.modules.events.templates import (
    DEFAULT_PARTICIPATION_FORMS,
    DEFAULT_STAGES,
    LISTENER_PARTICIPATION_FORMS,
    MODULES,
    TRANSITIONS,
    only_registration,
)
from app.modules.files.models import StoredFile


class EventError(Exception):
    """Ошибка операции с мероприятием."""

    pass


async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    # populate_existing перечитывает связи, если объект уже был в сессии (например, сразу после создания)
    """Мероприятие по id с перечитыванием связей или None."""
    return await session.get(Event, event_id, populate_existing=True)


async def get_by_slug(session: AsyncSession, slug: str) -> Event | None:
    """Мероприятие по адресу (slug) или None."""
    return await session.scalar(select(Event).where(Event.slug == slug))


async def slug_taken(session: AsyncSession, slug: str, exclude_id: int | None = None) -> bool:
    """Занят ли адрес; exclude_id исключает само мероприятие при переименовании."""
    query = select(func.count()).select_from(Event).where(Event.slug == slug)
    if exclude_id:
        query = query.where(Event.id != exclude_id)
    return bool(await session.scalar(query))


async def list_events(session: AsyncSession, user: User, scope: str = 'mine') -> list[Event]:
    """Мероприятия пользователя; суперпользователь с scope=all видит все."""
    query = select(Event).order_by(Event.date_start.desc().nulls_first(), Event.created_at.desc())
    if not (scope == 'all' and user.is_superuser):
        query = query.where(Event.id.in_(select(EventMember.event_id).where(EventMember.user_id == user.id)))
    return list((await session.scalars(query)).unique())


async def create_event(
    session: AsyncSession,
    user: User,
    title: str,
    slug: str,
    modules: dict[str, bool] | None = None,
    copy_from: Event | None = None,
) -> Event:
    """Создаёт мероприятие с выбранными разделами или копией другого; создатель становится организатором."""
    if await slug_taken(session, slug):
        raise EventError('Этот адрес уже занят')

    source_modules = copy_from.modules if copy_from is not None else {}
    selected = modules if modules is not None else source_modules or dict.fromkeys(MODULES, True)
    enabled = {module: bool(selected.get(module)) for module in MODULES}

    event = Event(
        title=title,
        slug=slug,
        created_by_id=user.id,
        modules=enabled,
        application_form=default_form(enabled),
    )
    if copy_from is not None:
        event.copied_from_id = copy_from.id
        for field in ('short_description', 'description', 'level', 'format', 'place', 'application_form'):
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
        stages = DEFAULT_STAGES if enabled['stages'] else ()
        forms = LISTENER_PARTICIPATION_FORMS if only_registration(enabled) else DEFAULT_PARTICIPATION_FORMS
        event.stages = [Stage(title=title_, kind=kind, order=i) for i, (title_, kind) in enumerate(stages)]
        event.participation_forms = [ParticipationForm(title=title_, order=i) for i, title_ in enumerate(forms)]
    event.members = [EventMember(user_id=user.id, role='organizer')]
    session.add(event)
    await session.flush()
    record(session, 'event.create', 'event', event.id, user.id, copied_from=copy_from and copy_from.id)
    return event


async def update_event(session: AsyncSession, user: User, event: Event, changes: dict) -> Event:
    """Применяет изменения полей с проверкой адреса, обложки и дат, пишет запись аудита."""
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
    """Проверяет согласованность дат мероприятия, приёма и заполнения заявок."""
    if event.date_start and event.date_end and event.date_end < event.date_start:
        raise EventError('Дата окончания раньше даты начала')
    opens, closes = event.registration_opens_at, event.registration_closes_at
    if opens and closes and closes <= opens:
        raise EventError('Приём заявок должен закрываться позже, чем открывается')
    details = event.details_closes_at
    if details and closes and details < closes:
        raise EventError('Заполнение заявок не может закончиться раньше приёма заявок')


async def change_status(session: AsyncSession, user: User, event: Event, new_status: str) -> Event:
    """Переводит мероприятие в новый статус по допустимым переходам; для публикации нужна дата начала."""
    if new_status not in TRANSITIONS[event.status]:
        raise EventError('Такой переход статуса недоступен')
    if new_status != 'draft' and not event.date_start:
        raise EventError('Перед публикацией укажите дату начала мероприятия')
    record(session, 'event.status', 'event', event.id, user.id, old=event.status, new=new_status)
    event.status = new_status
    await session.flush()
    return event


def registration_open(event: Event, at: datetime | None = None) -> bool:
    """Открыт ли приём новых заявок: статус мероприятия, модуль и окно дат."""
    if event.status != 'registration' or not event.modules.get('registration'):
        return False
    at = at or now_utc()
    if event.registration_opens_at and at < event.registration_opens_at:
        return False
    return not (event.registration_closes_at and at > event.registration_closes_at)


def details_open(event: Event, at: datetime | None = None) -> bool:
    """Можно ли дописывать подтверждённые заявки: своя дата, а без неё — пока идёт регистрация."""
    if event.status not in ('registration', 'running') or not event.modules.get('registration'):
        return False
    if event.details_closes_at:
        return (at or now_utc()) <= event.details_closes_at
    return registration_open(event, at)


# --- Направления, этапы, формы участия -----------------------------------------------------

CHILDREN = {'directions': Direction, 'stages': Stage, 'forms': ParticipationForm}
CHILD_ATTR = {'directions': 'directions', 'stages': 'stages', 'forms': 'participation_forms'}


async def add_child(session: AsyncSession, event: Event, kind: str, data: dict):
    """Добавляет в конец вложенного списка (направления, этапы, формы участия) новый элемент."""
    items = getattr(event, CHILD_ATTR[kind])
    child = CHILDREN[kind](**data, order=max((item.order for item in items), default=-1) + 1)
    items.append(child)
    await session.flush()
    return child


def find_child(event: Event, kind: str, child_id: int):
    """Элемент вложенного списка по id; если его нет, бросает EventError."""
    child = next((item for item in getattr(event, CHILD_ATTR[kind]) if item.id == child_id), None)
    if child is None:
        raise EventError('Элемент не найден')
    return child


async def reorder_children(session: AsyncSession, event: Event, kind: str, ids: list[int]) -> None:
    """Задаёт порядок элементов вложенного списка; нужно передать все id."""
    items = {item.id: item for item in getattr(event, CHILD_ATTR[kind])}
    if set(ids) != set(items):
        raise EventError('Передайте все элементы списка')
    for order, item_id in enumerate(ids):
        items[item_id].order = order
    getattr(event, CHILD_ATTR[kind]).sort(key=lambda item: item.order)
    await session.flush()


# --- Команда ---------------------------------------------------------------------------------


async def add_member(session: AsyncSession, actor: User, event: Event, user: User, role: str) -> EventMember:
    """Добавляет участника команды с ролью; повторное добавление той же роли ничего не меняет."""
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
    """Удаляет участника команды; единственного организатора удалить нельзя."""
    member = next((m for m in event.members if m.id == member_id), None)
    if member is None:
        raise EventError('Участник команды не найден')
    organizers = [m for m in event.members if m.role == 'organizer']
    if member.role == 'organizer' and len(organizers) == 1:
        raise EventError('Нельзя удалить единственного организатора')
    event.members.remove(member)
    record(session, 'event.member.remove', 'event', event.id, actor.id, user_id=member.user_id, role=member.role)
    await session.flush()
