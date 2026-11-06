"""Общее для роутеров заявок: права, загрузка заявки, ответы API."""

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sk_common.people.models import User

from app.modules.applications import service
from app.modules.applications.models import NEEDS_CHANGES, REQUESTED, SUBMITTED, Application
from app.modules.applications.moderation import allowed_decisions
from app.modules.applications.schemas import (
    ApplicationOut,
    ConsentOut,
    ContactOut,
    EventRef,
    FileRef,
    MemberOut,
    Ref,
)
from app.modules.events.models import Event
from app.modules.events.permissions import roles_of
from app.modules.events.service import get_event

STAFF = {'organizer', 'moderator'}


def error_response(exc: service.ApplicationError) -> JSONResponse:
    """Ошибка заявки: общее сообщение и ошибки по полям формы."""
    return JSONResponse({'detail': {'message': exc.message, 'errors': exc.errors}}, status_code=422)


def is_staff(user: User, event: Event) -> bool:
    """Организатор или модератор этого мероприятия."""
    return user.is_superuser or bool(STAFF & set(roles_of(user, event)))


async def load_app(db, app_id: int) -> Application:
    """Заявка по id, свежие данные из БД."""
    app = await db.get(Application, app_id, populate_existing=True)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return app


async def staff_app(db, app_id: int, user: User) -> Application:
    """Заявка для оргкомитета мероприятия. Чужим отвечаем так же, как если её нет."""
    app = await load_app(db, app_id)
    if not is_staff(user, app.event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Заявка не найдена')
    return app


async def staff_event(db, event_id: int, user: User) -> Event:
    """Мероприятие для оргкомитета."""
    event = await get_event(db, event_id)
    if event is None or not is_staff(user, event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    return event


def application_out(app: Application, user: User) -> ApplicationOut:
    """Заявка в ответе API. Исходные данные из внешней формы и решения видит только оргкомитет."""
    own = app.user_id == user.id
    staff = is_staff(user, app.event)
    return ApplicationOut(
        id=app.id,
        number=app.number,
        event=EventRef(id=app.event.id, slug=app.event.slug, title=app.event.title),
        status=app.status,
        source=app.source,
        title=app.title,
        direction=Ref(id=app.direction.id, title=app.direction.title) if app.direction else None,
        participation_form=Ref(id=app.participation_form.id, title=app.participation_form.title)
        if app.participation_form
        else None,
        answers=app.answers,
        contact=ContactOut(
            name=app.contact_name,
            email=app.contact_email,
            phone=app.contact_phone,
            organization=app.contact_organization,
            grade=app.contact_grade,
        ),
        is_linked=app.is_linked,
        raw_payload=app.raw_payload if staff else {},
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
        applicant_email=app.applicant_email,
        applicant_name=app.applicant_name,
        created_at=app.created_at,
        confirmed_at=app.confirmed_at,
        submitted_at=app.submitted_at,
        decided_at=app.decided_at,
        allowed_decisions=allowed_decisions(app) if staff else [],
        can_edit=own and service.can_edit(app),
        can_submit=own and service.can_edit(app),
        can_withdraw=own and app.status in {REQUESTED, 'draft', SUBMITTED, NEEDS_CHANGES},
        can_manage=staff,
    )
