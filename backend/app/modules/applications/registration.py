"""Первый шаг: общая заявка из открытой формы, от вошедшего пользователя или из внешнего приложения."""

from sk_common.audit import record
from sk_common.people.models import User
from sk_common.queue import Queue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications import form as forms
from app.modules.applications.models import REQUESTED, Application, Source
from app.modules.applications.notifications import notify
from app.modules.applications.schemas import RegistrationIn
from app.modules.applications.service import ApplicationError, choice_errors, event_form, make_consent, next_number
from app.modules.events.models import Event
from app.modules.events.service import registration_open

DEFAULT_SUCCESS_TEXT = (
    'Заявка получена. Когда организаторы её подтвердят, на почту придёт приглашение в личный кабинет.'
)


def success_message(form: forms.ApplicationForm) -> str:
    """Текст после отправки формы: свой у организатора или стандартный."""
    return form.registration.success_text or DEFAULT_SUCCESS_TEXT


def _contact(data: RegistrationIn, user: User | None) -> tuple[str, str, str]:
    """ФИО, email и организация заявки. Вошедшему пользователю подставляем данные из учётной записи."""
    if user is None:
        return ' '.join(data.full_name.split()), data.email.strip().lower(), data.organization.strip()
    person = user.person
    name = (person.full_name if person else '') or ' '.join(data.full_name.split())
    organization = data.organization.strip() or (person.organization if person else '') or ''
    return name, user.email, organization


def _check(
    event: Event, form: forms.ApplicationForm, data: RegistrationIn, user: User | None
) -> tuple[dict, dict[str, str]]:
    """Проверка данных открытой формы. Возвращает очищенные ответы и ошибки по полям."""
    settings = form.registration
    questions = [f for f in form.fields if f.on_registration]
    known = forms.ApplicationForm(fields=questions)
    answers, errors = forms.clean_answers(known, data.answers)
    errors |= forms.required_errors(questions, answers)
    errors |= choice_errors(event, data.direction_id, data.participation_form_id)
    if user is None:
        if not ' '.join(data.full_name.split()):
            errors['full_name'] = 'Укажите фамилию и имя'
        if not forms.EMAIL_RE.match(data.email.strip()):
            errors['email'] = 'Введите адрес электронной почты'
    if data.phone.strip() and not forms.PHONE_RE.match(data.phone.strip()):
        errors['phone'] = 'Введите номер телефона'
    if 'title' in settings.asked and not data.title.strip():
        errors['title'] = 'Укажите название работы'
    if 'direction' in settings.asked and event.directions and data.direction_id is None:
        errors['direction_id'] = 'Выберите направление'
    if 'participation_form' in settings.asked and event.participation_forms and data.participation_form_id is None:
        errors['participation_form_id'] = 'Выберите форму участия'
    accepted = set(data.consents)
    for consent in form.consents:
        if consent.required and consent.key not in accepted:
            errors[f'consent:{consent.key}'] = 'Нужно согласие'
    return answers, errors


async def _pending_duplicate(session: AsyncSession, event: Event, email: str, user: User | None) -> Application | None:
    """Такая же заявка уже ждёт подтверждения: повторная отправка формы не плодит копии."""
    owner = Application.user_id == user.id if user else func.lower(Application.contact_email) == email
    rows = await session.scalars(
        select(Application).where(Application.event_id == event.id, Application.status == REQUESTED, owner).limit(1)
    )
    return rows.unique().first()


def _build(
    event: Event,
    number: int,
    data: RegistrationIn,
    answers: dict,
    source: Source,
    user: User | None,
    contact: tuple[str, str, str],
) -> Application:
    """Новая заявка на первом шаге."""
    name, email, organization = contact
    return Application(
        event_id=event.id,
        number=number,
        user_id=user.id if user else None,
        source=source,
        status=REQUESTED,
        title=data.title.strip(),
        direction_id=data.direction_id,
        participation_form_id=data.participation_form_id,
        answers=answers,
        contact_name=name,
        contact_email=email,
        contact_phone=data.phone.strip(),
        contact_organization=organization,
        contact_grade=data.grade.strip(),
        members=[],
        consents=[],
        files=[],
    )


async def _after_create(session: AsyncSession, queue: Queue, app: Application, user: User | None) -> None:
    """Запись в журнал и письмо о получении заявки."""
    await session.flush()
    await session.refresh(app, ['event', 'user', 'direction', 'participation_form'])
    record(session, 'application.request', 'application', app.id, user.id if user else None, source=app.source)
    await notify(
        queue,
        app,
        'Заявка получена',
        f'Заявка №{app.number} получена. Когда организаторы её подтвердят, придёт приглашение заполнить остальное.',
    )


async def register(
    session: AsyncSession, event: Event, data: RegistrationIn, user: User | None, ip: str | None, queue: Queue
) -> Application:
    """Общая заявка из открытой формы или от вошедшего пользователя."""
    form = event_form(event)
    if not registration_open(event):
        raise ApplicationError('Приём заявок сейчас закрыт')
    if user is None and not form.registration.open_form:
        raise ApplicationError('Чтобы подать заявку, войдите в личный кабинет')
    answers, errors = _check(event, form, data, user)
    if errors:
        raise ApplicationError('Проверьте правильность заполнения', errors)

    contact = _contact(data, user)
    number = await next_number(session, event)  # блокировка мероприятия защищает и проверку на дубликат
    if duplicate := await _pending_duplicate(session, event, contact[1], user):
        return duplicate

    source = Source.CABINET if user else Source.FORM
    app = _build(event, number, data, answers, source, user, contact)
    accepted = set(data.consents)
    app.consents = [make_consent(c, user.id if user else None, ip) for c in form.consents if c.key in accepted]
    session.add(app)
    await _after_create(session, queue, app, user)
    return app


async def accept_webhook(
    session: AsyncSession, event: Event, data: RegistrationIn, external_id: str | None, raw: dict, queue: Queue
) -> Application | None:
    """Заявка из внешнего приложения. Повторная доставка той же записи ничего не меняет (вернётся None)."""
    number = await next_number(session, event)
    if external_id:
        known = await session.scalar(
            select(Application.id).where(Application.event_id == event.id, Application.external_id == external_id)
        )
        if known:
            return None
    app = _build(event, number, data, data.answers, Source.WEBHOOK, None, _contact(data, None))
    app.external_id = external_id
    app.raw_payload = raw
    session.add(app)
    await _after_create(session, queue, app, None)
    return app
