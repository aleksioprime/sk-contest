from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.deps import CurrentUser, Db
from app.core.queue import Queue, get_queue
from app.modules.applications import service
from app.modules.applications.export import applications_xlsx
from app.modules.applications.form import ApplicationForm, default_form
from app.modules.applications.models import ACCEPTED, NEEDS_CHANGES, SUBMITTED, Application
from app.modules.applications.schemas import (
    ApplicationListItem,
    ApplicationOut,
    ApplicationPage,
    ApplicationSave,
    BulkDecision,
    ConsentOut,
    Decision,
    EventRef,
    FileRef,
    MemberOut,
    PublicForm,
    Ref,
)
from app.modules.events.models import Event
from app.modules.events.permissions import ensure_manage, roles_of
from app.modules.events.service import get_by_slug, get_event, registration_open
from app.modules.people.models import User

router = APIRouter(prefix='/v1', tags=['applications'])

STAFF = {'organizer', 'moderator'}


def _error(exc: service.ApplicationError) -> JSONResponse:
    return JSONResponse({'detail': {'message': exc.message, 'errors': exc.errors}}, status_code=422)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get('x-forwarded-for', '')
    return forwarded.split(',')[0].strip() or (request.client.host if request.client else None)


def _is_staff(user: User, event: Event) -> bool:
    return user.is_superuser or bool(STAFF & set(roles_of(user, event)))


def _out(app: Application, user: User) -> ApplicationOut:
    own = app.user_id == user.id
    person = app.user.person
    return ApplicationOut(
        id=app.id,
        number=app.number,
        event=EventRef(id=app.event.id, slug=app.event.slug, title=app.event.title),
        status=app.status,
        title=app.title,
        direction=Ref(id=app.direction.id, title=app.direction.title) if app.direction else None,
        participation_form=Ref(id=app.participation_form.id, title=app.participation_form.title)
        if app.participation_form
        else None,
        answers=app.answers,
        members=[MemberOut.model_validate(m, from_attributes=True) for m in app.members],
        consents=[ConsentOut.model_validate(c, from_attributes=True) for c in app.consents],
        files=[
            FileRef(
                id=f.file.id,
                name=f.file.original_name,
                size=f.file.size,
                url=f'/api/v1/files/{f.file.id}',
                field_key=f.field_key,
            )
            for f in app.files
        ],
        moderator_comment=app.moderator_comment,
        applicant_email=app.user.email,
        applicant_name=person.full_name if person and person.full_name else app.user.email,
        created_at=app.created_at,
        submitted_at=app.submitted_at,
        decided_at=app.decided_at,
        can_edit=own and service.can_edit(app),
        can_submit=own and service.can_edit(app),
        can_withdraw=own and app.status in {'draft', SUBMITTED, NEEDS_CHANGES},
    )


async def _load_app(db, app_id: int) -> Application:
    app = await db.get(Application, app_id, populate_existing=True)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return app


async def _own_app(db, app_id: int, user: User) -> Application:
    app = await _load_app(db, app_id)
    if app.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return app


async def _staff_event(db, event_id: int, user: User) -> Event:
    event = await get_event(db, event_id)
    if event is None or not _is_staff(user, event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    return event


# --- Анкета ----------------------------------------------------------------------------------


@router.get('/public/events/{slug}/form', response_model=PublicForm, tags=['public'], summary='Анкета заявки')
async def public_form(slug: str, db: Db) -> PublicForm:
    event = await get_by_slug(db, slug)
    if event is None or event.status == 'draft' or not event.modules.get('registration'):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    return PublicForm(
        event=EventRef(id=event.id, slug=event.slug, title=event.title),
        form=service.event_form(event).model_dump(),
        directions=[Ref(id=d.id, title=d.title) for d in event.directions],
        participation_forms=[Ref(id=f.id, title=f.title) for f in event.participation_forms],
        registration_open=registration_open(event),
        registration_closes_at=event.registration_closes_at,
    )


@router.get('/events/{event_id}/form', summary='Анкета для редактирования')
async def get_form(event_id: int, db: Db, user: CurrentUser) -> dict:
    event = await _staff_event(db, event_id, user)
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
    event.application_form = default_form(event.type)
    await db.commit()
    return event.application_form


# --- Заявитель -------------------------------------------------------------------------------


@router.get('/my/applications', response_model=list[ApplicationOut], summary='Мои заявки')
async def my_applications(db: Db, user: CurrentUser) -> list[ApplicationOut]:
    rows = await db.scalars(
        select(Application).where(Application.user_id == user.id).order_by(Application.created_at.desc())
    )
    return [_out(app, user) for app in rows.unique()]


@router.post('/events/{slug}/applications', response_model=ApplicationOut, status_code=201, summary='Начать заявку')
async def start_application(slug: str, db: Db, user: CurrentUser):
    event = await get_by_slug(db, slug)
    if event is None or event.status == 'draft':
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    try:
        app = await service.create_draft(db, event, user)
    except service.ApplicationError as exc:
        return _error(exc)
    await db.commit()
    return _out(await _load_app(db, app.id), user)


@router.get('/applications/{app_id}', response_model=ApplicationOut, summary='Заявка')
async def get_application(app_id: int, db: Db, user: CurrentUser) -> ApplicationOut:
    app = await _load_app(db, app_id)
    if app.user_id != user.id and not _is_staff(user, app.event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return _out(app, user)


@router.put('/applications/{app_id}', response_model=ApplicationOut, summary='Сохранить заявку')
async def save_application(app_id: int, payload: ApplicationSave, request: Request, db: Db, user: CurrentUser):
    app = await _own_app(db, app_id, user)
    try:
        await service.save(db, app, user, payload, _client_ip(request))
    except service.ApplicationError as exc:
        return _error(exc)
    await db.commit()
    return _out(await _load_app(db, app.id), user)


@router.post('/applications/{app_id}/submit', response_model=ApplicationOut, summary='Отправить заявку')
async def submit_application(app_id: int, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]):
    app = await _own_app(db, app_id, user)
    try:
        await service.submit(db, app, user, queue)
    except service.ApplicationError as exc:
        return _error(exc)
    await db.commit()
    return _out(app, user)


@router.post('/applications/{app_id}/withdraw', response_model=ApplicationOut, summary='Отозвать заявку')
async def withdraw_application(app_id: int, db: Db, user: CurrentUser):
    app = await _own_app(db, app_id, user)
    try:
        await service.withdraw(db, app, user)
    except service.ApplicationError as exc:
        return _error(exc)
    await db.commit()
    return _out(app, user)


# --- Модерация -------------------------------------------------------------------------------


@router.get('/events/{event_id}/applications', response_model=ApplicationPage, summary='Заявки мероприятия')
async def event_applications(
    event_id: int,
    db: Db,
    user: CurrentUser,
    status_: Annotated[
        str, Query(alias='status', pattern='^(|submitted|needs_changes|accepted|rejected|withdrawn)$')
    ] = '',
    direction_id: int | None = None,
    search: str = '',
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApplicationPage:
    event = await _staff_event(db, event_id, user)
    items, total, counts = await service.list_for_event(db, event, status_, direction_id, search, offset, limit)
    return ApplicationPage(
        items=[
            ApplicationListItem(
                id=a.id,
                number=a.number,
                title=a.title,
                status=a.status,
                direction=a.direction.title if a.direction else '',
                participants=[m.full_name for m in a.members if m.role == 'participant'],
                supervisors=[m.full_name for m in a.members if m.role == 'supervisor'],
                applicant_email=a.user.email,
                submitted_at=a.submitted_at,
            )
            for a in items
        ],
        total=total,
        counts=counts,
    )


@router.post('/applications/{app_id}/decision', response_model=ApplicationOut, summary='Решение по заявке')
async def decide(
    app_id: int, payload: Decision, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]
):
    app = await _load_app(db, app_id)
    if not _is_staff(user, app.event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    try:
        await service.decide(db, app, user, payload.status, payload.comment, queue)
    except service.ApplicationError as exc:
        return _error(exc)
    await db.commit()
    return _out(app, user)


@router.post('/events/{event_id}/applications/decision', summary='Решение по нескольким заявкам')
async def bulk_decide(
    event_id: int, payload: BulkDecision, db: Db, user: CurrentUser, queue: Annotated[Queue, Depends(get_queue)]
):
    event = await _staff_event(db, event_id, user)
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
            await service.decide(db, app, user, payload.status, payload.comment, queue)
        except service.ApplicationError:
            skipped.append(app.number)
    await db.commit()
    return {'updated': len(apps) - len(skipped), 'skipped': sorted(skipped)}


@router.get('/events/{event_id}/applications/export.xlsx', summary='Выгрузить заявки в Excel')
async def export_applications(event_id: int, db: Db, user: CurrentUser, only_accepted: bool = False) -> Response:
    event = await _staff_event(db, event_id, user)
    query = select(Application).where(Application.event_id == event.id, Application.status != 'draft')
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
