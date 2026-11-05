"""Первый шаг заявки: открытая форма, вебхук для внешних приложений и его настройка."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sk_common.auth.router import client_info
from sk_common.captcha import Captcha, get_captcha
from sk_common.deps import CurrentUser, Db, OptionalUser
from sk_common.queue import Queue, get_queue
from sk_common.redis import get_redis, hit_limit
from sqlalchemy import select

from app.core.letters import app_link
from app.modules.applications import registration, service, webhook
from app.modules.applications.router_common import error_response
from app.modules.applications.schemas import (
    OpenEvent,
    PublicEvent,
    PublicForm,
    Ref,
    RegistrationIn,
    RegistrationResult,
    WebhookOut,
)
from app.modules.events.models import Event
from app.modules.events.permissions import ensure_manage
from app.modules.events.service import get_by_slug, get_event, registration_open

router = APIRouter(prefix='/v1', tags=['registration'])
public_router = APIRouter(prefix='/v1/public', tags=['public'])

# Лимиты: сколько заявок принимаем с одного адреса и через один вебхук за час
FORM_PER_IP_HOUR = 20
WEBHOOK_PER_HOUR = 600
WEBHOOK_STATUSES = {'registration', 'running'}


def _public_event(event: Event) -> PublicEvent:
    """Данные мероприятия для страницы формы."""
    return PublicEvent(
        id=event.id,
        slug=event.slug,
        title=event.title,
        short_description=event.short_description,
        description=event.description,
        place=event.place,
        date_start=event.date_start,
        date_end=event.date_end,
        cover_url=f'/api/v1/public/files/{event.cover_file_id}' if event.cover_file_id else None,
    )


def _webhook_url(event: Event) -> str | None:
    """Адрес вебхука мероприятия для настройки во внешней форме."""
    return app_link(f'/api/v1/public/webhooks/{event.webhook_token}') if event.webhook_token else None


async def _published_event(db, slug: str) -> Event:
    """Опубликованное мероприятие с регистрацией, иначе 404."""
    event = await get_by_slug(db, slug)
    if event is None or event.status == 'draft' or not event.modules.get('registration'):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    return event


# --- Открытая форма --------------------------------------------------------------------------


@public_router.get('/events', response_model=list[OpenEvent], summary='Мероприятия с открытым приёмом заявок')
async def open_events(db: Db) -> list[OpenEvent]:
    rows = await db.scalars(select(Event).where(Event.status == 'registration').order_by(Event.date_start))
    return [OpenEvent.model_validate(e, from_attributes=True) for e in rows.unique() if registration_open(e)]


@public_router.get('/events/{slug}/form', response_model=PublicForm, summary='Анкета и настройки открытой формы')
async def public_form(slug: str, db: Db) -> PublicForm:
    event = await _published_event(db, slug)
    form = service.event_form(event).model_dump()
    del form['registration']['webhook_fields']  # имена полей внешней формы посетителю не нужны
    return PublicForm(
        event=_public_event(event),
        form=form,
        directions=[Ref(id=d.id, title=d.title) for d in event.directions],
        participation_forms=[Ref(id=f.id, title=f.title) for f in event.participation_forms],
        registration_open=registration_open(event),
        registration_closes_at=event.registration_closes_at,
    )


@public_router.post(
    '/events/{slug}/register', response_model=RegistrationResult, status_code=201, summary='Оставить общую заявку'
)
async def register(
    slug: str,
    payload: RegistrationIn,
    request: Request,
    db: Db,
    user: OptionalUser,
    queue: Annotated[Queue, Depends(get_queue)],
    captcha: Annotated[Captcha, Depends(get_captcha)],
):
    event = await _published_event(db, slug)
    _, ip = client_info(request)
    if user is None:
        if not await captcha.verify(payload.captcha_token, ip):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Подтвердите, что вы не робот')
        if ip and await hit_limit(get_redis(), f'register-ip:{ip}', FORM_PER_IP_HOUR, 3600):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, 'Слишком много заявок. Попробуйте через час.')
    try:
        app = await registration.register(db, event, payload, user, ip, queue)
    except service.ApplicationError as exc:
        return error_response(exc)
    await db.commit()
    return RegistrationResult(
        message=registration.success_message(service.event_form(event)),
        application_id=app.id if user else None,
    )


# --- Вебхук ----------------------------------------------------------------------------------


@public_router.post('/webhooks/{token}', response_class=PlainTextResponse, summary='Заявка из внешнего приложения')
async def incoming_webhook(token: str, request: Request, db: Db, queue: Annotated[Queue, Depends(get_queue)]) -> str:
    """Принимает JSON или форму. Секрет — в адресе; ответ «ok» — то, чего ждёт Tilda."""
    event = await db.scalar(select(Event).where(Event.webhook_token == token))
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Вебхук не найден')
    if len(await request.body()) > webhook.MAX_BODY:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, 'Слишком большой запрос')
    try:
        payload = await webhook.read_payload(request)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Не удалось разобрать запрос') from exc
    if webhook.is_test_request(payload):
        return 'ok'
    # После закрытия окна заявку всё равно принимаем: посетитель внешнего сайта уже её отправил, решит модератор
    if event.status not in WEBHOOK_STATUSES or not event.modules.get('registration'):
        raise HTTPException(status.HTTP_409_CONFLICT, 'Мероприятие сейчас не принимает заявки')
    if await hit_limit(get_redis(), f'webhook:{event.id}', WEBHOOK_PER_HOUR, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, 'Слишком много заявок')
    data, external_id, raw = webhook.parse(event, service.event_form(event), payload)
    if not data.full_name and not data.email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, 'В заявке нет ни имени, ни email')
    await registration.accept_webhook(db, event, data, external_id, raw, queue)
    await db.commit()
    return 'ok'


async def _managed_event(db, event_id: int, user) -> Event:
    """Мероприятие для организатора."""
    event = await get_event(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
    ensure_manage(user, event)
    return event


@router.get('/events/{event_id}/webhook', response_model=WebhookOut, summary='Адрес вебхука')
async def get_webhook(event_id: int, db: Db, user: CurrentUser) -> WebhookOut:
    return WebhookOut(url=_webhook_url(await _managed_event(db, event_id, user)))


@router.post('/events/{event_id}/webhook', response_model=WebhookOut, summary='Включить вебхук или сменить его адрес')
async def enable_webhook(event_id: int, db: Db, user: CurrentUser) -> WebhookOut:
    event = await _managed_event(db, event_id, user)
    event.webhook_token = secrets.token_urlsafe(32)
    await db.commit()
    return WebhookOut(url=_webhook_url(event))


@router.delete('/events/{event_id}/webhook', response_model=WebhookOut, summary='Выключить вебхук')
async def disable_webhook(event_id: int, db: Db, user: CurrentUser) -> WebhookOut:
    event = await _managed_event(db, event_id, user)
    event.webhook_token = None
    await db.commit()
    return WebhookOut(url=None)
