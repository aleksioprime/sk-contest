"""Заявки: анкета мероприятия, кабинет заявителя и работа оргкомитета."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sk_common.audit import record
from sk_common.auth.router import client_info
from sk_common.deps import CurrentUser, Db
from sk_common.people.models import User
from sk_common.queue import Queue, get_queue
from sqlalchemy import select

from app.modules.applications import moderation, service
from app.modules.applications.export import applications_xlsx
from app.modules.applications.form import ApplicationForm, default_form
from app.modules.applications.models import ACCEPTED, Application
from app.modules.applications.router_common import application_out, error_response, load_app, staff_app, staff_event
from app.modules.applications.schemas import (
    ApplicationListItem,
    ApplicationOut,
    ApplicationPage,
    ApplicationSave,
    BulkDecision,
    ContactIn,
    Decision,
    LinkPerson,
    PersonMatch,
    StaffApplication,
)
from app.modules.events.permissions import ensure_manage
from app.modules.events.service import get_event

router = APIRouter(prefix='/v1', tags=['applications'])

STATUS_FILTER = '^(|requested|draft|submitted|needs_changes|accepted|rejected|withdrawn)$'


async def _own_app(db, app_id: int, user: User) -> Application:
    """Заявка самого пользователя. Чужим отвечаем так же, как если её нет."""
    app = await load_app(db, app_id)
    if app.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return app


# --- Анкета ----------------------------------------------------------------------------------


@router.get('/events/{event_id}/form', summary='Анкета для редактирования')
async def get_form(event_id: int, db: Db, user: CurrentUser) -> dict:
    event = await staff_event(db, event_id, user)
    return service.event_form(event).model_dump()


@router.put('/events/{event_id}/form', summary='Сохранить анкету')
async def put_form(event_id: int, payload: ApplicationForm, db: Db, user: CurrentUser) -> dict:
    event = await get_event(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    ensure_manage(user, event)
    event.application_form = payload.model_dump()
    await db.commit()
    return event.application_form


@router.post('/events/{event_id}/form/reset', summary='Вернуть анкету по умолчанию')
async def reset_form(event_id: int, db: Db, user: CurrentUser) -> dict:
    event = await get_event(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    ensure_manage(user, event)
    event.application_form = default_form(event.modules)
    await db.commit()
    return event.application_form


# --- Заявитель -------------------------------------------------------------------------------


@router.get('/my/applications', response_model=list[ApplicationOut], summary='Мои заявки')
async def my_applications(db: Db, user: CurrentUser) -> list[ApplicationOut]:
    rows = await db.scalars(
        select(Application).where(Application.user_id == user.id).order_by(Application.created_at.desc())
    )
    return [application_out(app, user) for app in rows.unique()]


@router.get('/applications/{app_id}', response_model=ApplicationOut, summary='Заявка')
async def get_application(app_id: int, db: Db, user: CurrentUser) -> ApplicationOut:
    app = await load_app(db, app_id)
    if app.user_id != user.id:
        app = await staff_app(db, app_id, user)
    return application_out(app, user)


@router.put('/applications/{app_id}', response_model=ApplicationOut, summary='Сохранить заявку')
async def save_application(app_id: int, payload: ApplicationSave, request: Request, db: Db, user: CurrentUser):
    app = await _own_app(db, app_id, user)
    try:
        await service.save(db, app, user, payload, client_info(request)[1])
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.post('/applications/{app_id}/submit', response_model=ApplicationOut, summary='Отправить заявку')
async def submit_application(app_id: int, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]):
    app = await _own_app(db, app_id, user)
    try:
        await service.submit(db, app, user, queue)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(app, user)


@router.post('/applications/{app_id}/withdraw', response_model=ApplicationOut, summary='Отозвать заявку')
async def withdraw_application(app_id: int, db: Db, user: CurrentUser):
    app = await _own_app(db, app_id, user)
    try:
        await service.withdraw(db, app, user)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(app, user)


# --- Модерация -------------------------------------------------------------------------------


@router.get('/events/{event_id}/applications', response_model=ApplicationPage, summary='Заявки мероприятия')
async def event_applications(
    event_id: int,
    db: Db,
    user: CurrentUser,
    status_: Annotated[str, Query(alias='status', pattern=STATUS_FILTER)] = '',
    direction_id: int | None = None,
    search: str = '',
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApplicationPage:
    event = await staff_event(db, event_id, user)
    items, total, counts = await service.list_for_event(db, event, status_, direction_id, search, offset, limit)
    return ApplicationPage(
        items=[
            ApplicationListItem(
                id=a.id,
                number=a.number,
                title=a.title,
                status=a.status,
                source=a.source,
                direction=a.direction.title if a.direction else '',
                participants=[m.full_name for m in a.members if m.role == 'participant'],
                supervisors=[m.full_name for m in a.members if m.role == 'supervisor'],
                applicant_name=a.applicant_name,
                applicant_email=a.applicant_email,
                is_linked=a.user_id is not None,
                created_at=a.created_at,
                submitted_at=a.submitted_at,
            )
            for a in items
        ],
        total=total,
        counts=counts,
    )


@router.post(
    '/events/{event_id}/applications/manual',
    response_model=ApplicationOut,
    status_code=201,
    summary='Заявка от оргкомитета',
)
async def create_by_staff(event_id: int, payload: StaffApplication, request: Request, db: Db, user: CurrentUser):
    event = await staff_event(db, event_id, user)
    try:
        app = await service.create_by_staff(db, event, user, payload, client_info(request)[1])
    except service.ApplicationError as exc:
        await db.rollback()
        return error_response(exc)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.put('/applications/{app_id}/manage', response_model=ApplicationOut, summary='Правка заявки оргкомитетом')
async def save_by_staff(app_id: int, payload: ApplicationSave, request: Request, db: Db, user: CurrentUser):
    app = await staff_app(db, app_id, user)
    try:
        await service.save(db, app, user, payload, client_info(request)[1], staff=True)
    except service.ApplicationError as exc:
        return error_response(exc)
    record(db, 'application.edit_by_staff', 'application', app.id, user.id)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.post('/applications/{app_id}/decision', response_model=ApplicationOut, summary='Решение по заявке')
async def decide(
    app_id: int, payload: Decision, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]
):
    app = await staff_app(db, app_id, user)
    try:
        await moderation.decide(db, app, user, payload.status, payload.comment, queue)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.post('/events/{event_id}/applications/decision', summary='Решение по нескольким заявкам')
async def bulk_decide(
    event_id: int, payload: BulkDecision, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]
):
    event = await staff_event(db, event_id, user)
    apps = list(
        (
            await db.scalars(
                select(Application).where(Application.event_id == event.id, Application.id.in_(payload.ids))
            )
        ).unique()
    )
    skipped = []
    for app in apps:
        try:
            await moderation.decide(db, app, user, payload.status, payload.comment, queue)
        except service.ApplicationError:
            skipped.append(app.number)
    await db.commit()
    return {'updated': len(apps) - len(skipped), 'skipped': sorted(skipped)}


@router.get('/events/{event_id}/applications/export.xlsx', summary='Выгрузить заявки в Excel')
async def export_applications(event_id: int, db: Db, user: CurrentUser, only_accepted: bool = False) -> Response:
    event = await staff_event(db, event_id, user)
    query = select(Application).where(Application.event_id == event.id)
    if only_accepted:
        query = query.where(Application.status == ACCEPTED)
    apps = list((await db.scalars(query.order_by(Application.number))).unique())
    content = applications_xlsx(apps, service.event_form(event))
    filename = quote(f'Заявки — {event.title}.xlsx')
    return Response(
        content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}"},
    )


# --- Заявитель и человек из базы -------------------------------------------------------------


@router.get('/events/{event_id}/people', response_model=list[PersonMatch], summary='Поиск людей для связи с заявкой')
async def search_people(event_id: int, db: Db, user: CurrentUser, q: str = '') -> list[PersonMatch]:
    await staff_event(db, event_id, user)
    return await moderation.search_people(db, q)


@router.get('/applications/{app_id}/matches', response_model=list[PersonMatch], summary='Похожие люди в базе')
async def application_matches(app_id: int, db: Db, user: CurrentUser) -> list[PersonMatch]:
    return await moderation.find_matches(db, await staff_app(db, app_id, user))


@router.put('/applications/{app_id}/person', response_model=ApplicationOut, summary='Связать заявку с человеком')
async def link_person(app_id: int, payload: LinkPerson, db: Db, user: CurrentUser):
    app = await staff_app(db, app_id, user)
    try:
        await moderation.link_person(db, app, user, payload.person_id)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.delete('/applications/{app_id}/person', response_model=ApplicationOut, summary='Снять связь с человеком')
async def unlink_person(app_id: int, db: Db, user: CurrentUser):
    app = await staff_app(db, app_id, user)
    try:
        await moderation.unlink_person(db, app, user)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.put('/applications/{app_id}/contact', response_model=ApplicationOut, summary='Исправить контакты заявителя')
async def update_contact(app_id: int, payload: ContactIn, db: Db, user: CurrentUser) -> ApplicationOut:
    app = await staff_app(db, app_id, user)
    await moderation.update_contact(db, app, user, payload)
    await db.commit()
    return application_out(await load_app(db, app.id), user)


@router.post('/applications/{app_id}/invite', response_model=ApplicationOut, summary='Отправить приглашение ещё раз')
async def resend_invitation(app_id: int, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]):
    app = await staff_app(db, app_id, user)
    try:
        await moderation.resend_invitation(db, app, user, queue)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return application_out(app, user)
