"""Эндпоинты мероприятий: список, настройки, статусы, вложенные списки и команда."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sk_common.audit import record
from sk_common.deps import CurrentUser, Db
from sk_common.people.models import User
from sk_common.people.service import find_or_create_user_by_email

from app.modules.evaluation.service import copy_evaluation_setup
from app.modules.events import service
from app.modules.events.models import Event
from app.modules.events.permissions import can_create_event, can_manage, ensure_manage, ensure_view, roles_of
from app.modules.events.schemas import (
    DirectionIn,
    DirectionOut,
    EventCreate,
    EventListItem,
    EventOut,
    EventUpdate,
    FormIn,
    FormOut,
    MemberIn,
    MemberOut,
    Reorder,
    StageIn,
    StageOut,
    StatusChange,
)
from app.modules.events.templates import TRANSITIONS

router = APIRouter(prefix='/v1/events', tags=['events'])

CHILD_SCHEMAS = {'directions': (DirectionIn, DirectionOut), 'stages': (StageIn, StageOut), 'forms': (FormIn, FormOut)}


def _bad_request(exc: Exception) -> HTTPException:
    """Превращает ошибку бизнес-логики в ответ 400."""
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _load(db, event_id: int, user: User, manage: bool = False) -> Event:
    """Возвращает мероприятие с проверкой просмотра и (при manage) управления; если его нет, отвечает 404."""
    event = await service.get_event(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    ensure_view(user, event)
    if manage:
        ensure_manage(user, event)
    return event


def _out(event: Event, user: User) -> EventOut:
    """Схема мероприятия с ролями пользователя, правом управления и допустимыми статусами."""
    result = EventOut.model_validate(event)
    result.my_roles = roles_of(user, event)
    result.can_manage = can_manage(user, event)
    result.allowed_statuses = sorted(TRANSITIONS[event.status]) if result.can_manage else []
    return result


def _member_out(member) -> MemberOut:
    """Схема участника команды с именем из профиля или email."""
    person = member.user.person
    return MemberOut(
        id=member.id,
        user_id=member.user_id,
        email=member.user.email,
        full_name=person.full_name if person and person.full_name else member.user.email,
        role=member.role,
    )


@router.get('', response_model=list[EventListItem], summary='Мои мероприятия')
async def list_events(
    db: Db, user: CurrentUser, scope: Annotated[str, Query(pattern='^(mine|all)$')] = 'mine'
) -> list[EventListItem]:
    events = await service.list_events(db, user, scope)
    return [
        EventListItem(
            id=e.id,
            slug=e.slug,
            title=e.title,
            status=e.status,
            date_start=e.date_start,
            date_end=e.date_end,
            my_roles=roles_of(user, e),
        )
        for e in events
    ]


@router.get('/slug-available', summary='Проверить адрес мероприятия')
async def slug_available(db: Db, _: CurrentUser, slug: str, exclude_id: int | None = None) -> dict:
    return {'available': not await service.slug_taken(db, slug, exclude_id)}


@router.post('', response_model=EventOut, status_code=status.HTTP_201_CREATED, summary='Создать мероприятие')
async def create_event(payload: EventCreate, db: Db, user: CurrentUser) -> EventOut:
    if not can_create_event(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Создавать мероприятия могут сотрудники гимназии')
    copy_from = None
    if payload.copy_from_id:
        copy_from = await _load(db, payload.copy_from_id, user)
    try:
        event = await service.create_event(db, user, payload.title, payload.slug, payload.modules, copy_from)
        if copy_from is not None and event.modules.get('evaluation'):
            await copy_evaluation_setup(db, copy_from.id, event.id)
    except service.EventError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(await service.get_event(db, event.id), user)


@router.get('/{event_id}', response_model=EventOut, summary='Мероприятие')
async def get_event(event_id: int, db: Db, user: CurrentUser) -> EventOut:
    return _out(await _load(db, event_id, user), user)


@router.patch('/{event_id}', response_model=EventOut, summary='Изменить мероприятие')
async def update_event(event_id: int, payload: EventUpdate, db: Db, user: CurrentUser) -> EventOut:
    event = await _load(db, event_id, user, manage=True)
    try:
        await service.update_event(db, user, event, payload.model_dump(exclude_unset=True))
    except service.EventError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(event, user)


@router.post('/{event_id}/status', response_model=EventOut, summary='Сменить статус')
async def change_status(event_id: int, payload: StatusChange, db: Db, user: CurrentUser) -> EventOut:
    event = await _load(db, event_id, user, manage=True)
    try:
        await service.change_status(db, user, event, payload.status)
    except service.EventError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _out(event, user)


@router.delete('/{event_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Удалить черновик')
async def delete_event(event_id: int, db: Db, user: CurrentUser) -> Response:
    event = await _load(db, event_id, user, manage=True)
    if event.status != 'draft':
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Удалить можно только черновик. Остальные — в архив.')
    record(db, 'event.delete', 'event', event.id, user.id, slug=event.slug)
    await db.delete(event)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Направления, этапы, формы участия -----------------------------------------------------


def _child_routes(kind: str) -> None:
    """Регистрирует эндпоинты добавления, изменения, удаления и сортировки для вложенного списка kind."""
    schema_in, schema_out = CHILD_SCHEMAS[kind]

    @router.post(f'/{{event_id}}/{kind}', response_model=schema_out, status_code=201, name=f'add_{kind}')
    async def add(event_id: int, payload: schema_in, db: Db, user: CurrentUser):
        """Добавляет элемент вложенного списка."""
        event = await _load(db, event_id, user, manage=True)
        child = await service.add_child(db, event, kind, payload.model_dump())
        await db.commit()
        return child

    @router.patch(f'/{{event_id}}/{kind}/{{child_id}}', response_model=schema_out, name=f'update_{kind}')
    async def update(event_id: int, child_id: int, payload: schema_in, db: Db, user: CurrentUser):
        """Заменяет поля элемента вложенного списка."""
        event = await _load(db, event_id, user, manage=True)
        try:
            child = service.find_child(event, kind, child_id)
        except service.EventError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        for field, value in payload.model_dump().items():
            setattr(child, field, value)
        await db.commit()
        return child

    @router.delete(f'/{{event_id}}/{kind}/{{child_id}}', status_code=204, name=f'delete_{kind}')
    async def delete(event_id: int, child_id: int, db: Db, user: CurrentUser) -> Response:
        """Удаляет элемент вложенного списка."""
        event = await _load(db, event_id, user, manage=True)
        try:
            child = service.find_child(event, kind, child_id)
        except service.EventError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        await db.delete(child)
        await db.commit()
        return Response(status_code=204)

    @router.put(f'/{{event_id}}/{kind}/order', status_code=204, name=f'reorder_{kind}')
    async def reorder(event_id: int, payload: Reorder, db: Db, user: CurrentUser) -> Response:
        """Сохраняет порядок элементов вложенного списка."""
        event = await _load(db, event_id, user, manage=True)
        try:
            await service.reorder_children(db, event, kind, payload.ids)
        except service.EventError as exc:
            raise _bad_request(exc) from exc
        await db.commit()
        return Response(status_code=204)


for _kind in CHILD_SCHEMAS:
    _child_routes(_kind)


# --- Команда ---------------------------------------------------------------------------------


@router.get('/{event_id}/members', response_model=list[MemberOut], summary='Команда мероприятия')
async def list_members(event_id: int, db: Db, user: CurrentUser) -> list[MemberOut]:
    event = await _load(db, event_id, user)
    return [_member_out(m) for m in sorted(event.members, key=lambda m: (m.role, m.user.email))]


@router.post('/{event_id}/members', response_model=MemberOut, status_code=201, summary='Добавить в команду')
async def add_member(event_id: int, payload: MemberIn, db: Db, user: CurrentUser) -> MemberOut:
    event = await _load(db, event_id, user, manage=True)
    target = await find_or_create_user_by_email(db, payload.email)
    member = await service.add_member(db, user, event, target, payload.role)
    await db.commit()
    return _member_out(member)


@router.delete('/{event_id}/members/{member_id}', status_code=204, summary='Убрать из команды')
async def remove_member(event_id: int, member_id: int, db: Db, user: CurrentUser) -> Response:
    event = await _load(db, event_id, user, manage=True)
    try:
        await service.remove_member(db, user, event, member_id)
    except service.EventError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return Response(status_code=204)
