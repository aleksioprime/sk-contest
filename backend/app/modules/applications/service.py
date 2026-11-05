"""Анкета заявки в кабинете (второй шаг): сохранение, проверка и отправка; заявка от оргкомитета; список заявок."""

from sk_common.audit import record
from sk_common.people.models import User
from sk_common.people.service import find_or_create_user_by_email
from sk_common.queue import Queue
from sk_common.security import now_utc
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications import form as forms
from app.modules.applications.models import (
    ACCEPTED,
    ACTIVE,
    DRAFT,
    EDITABLE,
    NEEDS_CHANGES,
    REJECTED,
    REQUESTED,
    SUBMITTED,
    WITHDRAWN,
    Application,
    ApplicationConsent,
    ApplicationFile,
    ApplicationMember,
    Source,
)
from app.modules.applications.notifications import notify
from app.modules.applications.schemas import ApplicationSave
from app.modules.events.models import Event
from app.modules.events.service import details_open
from app.modules.files.models import StoredFile

STATUS_TITLES = {
    REQUESTED: 'ждёт подтверждения',
    DRAFT: 'заполняется',
    SUBMITTED: 'на рассмотрении',
    NEEDS_CHANGES: 'нужны правки',
    ACCEPTED: 'принята',
    REJECTED: 'отклонена',
    WITHDRAWN: 'отозвана',
}
SOURCE_TITLES = {
    Source.FORM: 'открытая форма',
    Source.WEBHOOK: 'внешняя форма',
    Source.CABINET: 'личный кабинет',
    Source.STAFF: 'оргкомитет',
    Source.IMPORT: 'архив',
}


class ApplicationError(Exception):
    """Ошибка заявки: общее сообщение и ошибки по полям формы."""

    def __init__(self, message: str, errors: dict[str, str] | None = None):
        """Принимает общее сообщение и ошибки по ключам полей."""
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


def event_form(event: Event) -> forms.ApplicationForm:
    """Анкета мероприятия; у мероприятий без своей анкеты — по умолчанию для типа."""
    return forms.parse_form(event.application_form or forms.default_form(event.type))


def can_edit(app: Application) -> bool:
    """Может ли заявитель сейчас менять анкету."""
    if app.status == NEEDS_CHANGES:
        return True
    return app.status == DRAFT and details_open(app.event)


async def next_number(session: AsyncSession, event: Event) -> int:
    """Следующий номер заявки. Блокировка мероприятия не даёт двум запросам взять один номер."""
    locked = await session.scalar(select(Event.id).where(Event.id == event.id).with_for_update())
    return ((await session.scalar(select(func.max(Application.number)).where(Application.event_id == locked))) or 0) + 1


def make_consent(consent: forms.Consent, user_id: int | None, ip: str | None) -> ApplicationConsent:
    """Запись о том, что текст согласия принят сейчас."""
    return ApplicationConsent(
        key=consent.key,
        version=consent.version,
        title=consent.title,
        user_id=user_id,
        ip=ip,
        accepted_at=now_utc(),
    )


# --- Заявка от оргкомитета -----------------------------------------------------------------


async def create_by_staff(session: AsyncSession, event: Event, actor: User, data, ip: str | None) -> Application:
    """Заявка, которую вносит оргкомитет (приём на месте, заявки по почте). Окно приёма не проверяется.

    Владелец — контактное лицо по email (увидит заявку в кабинете) или сам сотрудник.
    Согласия на обработку данных в этом случае собирает оргкомитет, в заявке они не отмечаются.
    """
    owner = await find_or_create_user_by_email(session, data.owner_email) if data.owner_email else actor
    number = await next_number(session, event)
    now = now_utc()
    app = Application(
        event_id=event.id,
        number=number,
        user_id=owner.id,
        source=Source.STAFF,
        contact_email=owner.email,
        members=[],
        consents=[],
        files=[],
    )
    session.add(app)
    await session.flush()
    await session.refresh(app, ['event'])
    await save(session, app, actor, data, ip, staff=True)
    app.status = data.status
    app.confirmed_at = app.submitted_at = now
    if data.status == ACCEPTED:
        app.decided_at = now
        app.decided_by_id = actor.id
    record(session, 'application.create_by_staff', 'application', app.id, actor.id, event_id=event.id)
    await session.flush()
    return app


# --- Анкета в кабинете ---------------------------------------------------------------------


async def save(
    session: AsyncSession, app: Application, user: User, data: ApplicationSave, ip: str | None, staff: bool = False
) -> None:
    """Сохранить анкету. staff — правка оргкомитетом: в любом статусе, файлы загружает сотрудник."""
    if not staff and not can_edit(app):
        raise ApplicationError('Эту заявку сейчас нельзя изменить')
    event = app.event
    form = event_form(event)

    answers, errors = forms.clean_answers(form, data.answers)
    errors |= choice_errors(event, data.direction_id, data.participation_form_id)

    participants = [m for m in data.members if m.role == 'participant']
    supervisors = [m for m in data.members if m.role == 'supervisor']
    max_participants = form.team.max if form.team.enabled else 1
    if len(participants) > max_participants:
        errors['members'] = f'Участников не может быть больше {max_participants}'
    if len(supervisors) > form.team.supervisors_max:
        errors['members'] = f'Руководителей не может быть больше {form.team.supervisors_max}'

    file_ids = {key: value for key, value in answers.items() if form_field_type(form, key) == 'file' and value}
    if file_ids:
        # Файл должен быть своим или уже прикреплённым: сотрудник и новый владелец не теряют файлы заявки
        attached = {f.file_id for f in app.files}
        owned = set(
            await session.scalars(
                select(StoredFile.id).where(StoredFile.id.in_(file_ids.values()), StoredFile.owner_id == user.id)
            )
        )
        for key, file_id in file_ids.items():
            if file_id not in owned | attached:
                errors[key] = 'Файл не найден, загрузите его заново'
    if errors:
        raise ApplicationError('Проверьте правильность заполнения', errors)

    app.title = data.title.strip()
    app.direction_id = data.direction_id
    app.participation_form_id = data.participation_form_id
    app.answers = answers
    # Связь участника с человеком из базы не приходит с формы: сохраняем её по совпадению ФИО
    known_persons = {(m.role, m.full_name): m.person_id for m in app.members}
    app.members = [
        ApplicationMember(**m.model_dump(), person_id=known_persons.get((m.role, m.full_name)), order=i)
        for i, m in enumerate(data.members)
    ]
    app.files = [ApplicationFile(file_id=file_id, field_key=key) for key, file_id in file_ids.items()]

    accepted = set(data.consents)
    kept = [c for c in app.consents if c.key in accepted]
    for consent in form.consents:
        current = next((c for c in kept if c.key == consent.key), None)
        if consent.key in accepted and (current is None or current.version != consent.version):
            if current:
                kept.remove(current)
            kept.append(make_consent(consent, user.id, ip))
    app.consents = kept
    await session.flush()


def choice_errors(event: Event, direction_id: int | None, participation_form_id: int | None) -> dict[str, str]:
    """Направление и форма участия должны относиться к этому мероприятию."""
    errors = {}
    if direction_id is not None and direction_id not in {d.id for d in event.directions}:
        errors['direction_id'] = 'Выберите направление из списка'
    if participation_form_id is not None and participation_form_id not in {f.id for f in event.participation_forms}:
        errors['participation_form_id'] = 'Выберите форму участия из списка'
    return errors


def form_field_type(form: forms.ApplicationForm, key: str) -> str | None:
    """Тип поля анкеты по ключу."""
    return next((f.type for f in form.fields if f.key == key), None)


async def validate_for_submit(session: AsyncSession, app: Application) -> dict[str, str]:
    """Полная проверка анкеты перед отправкой: обязательные поля, команда, согласия и лимиты."""
    event = app.event
    form = event_form(event)
    errors = forms.required_errors(form.fields, app.answers)
    if not app.title:
        errors['title'] = 'Укажите название работы'
    if event.directions and app.direction_id is None:
        errors['direction_id'] = 'Выберите направление'
    if event.participation_forms and app.participation_form_id is None:
        errors['participation_form_id'] = 'Выберите форму участия'

    participants = [m for m in app.members if m.role == 'participant']
    supervisors = [m for m in app.members if m.role == 'supervisor']
    min_participants = form.team.min if form.team.enabled else 1
    if len(participants) < min_participants:
        errors['members'] = f'Добавьте участников: не меньше {min_participants}'
    elif form.team.require_supervisor and not supervisors:
        errors['members'] = 'Укажите руководителя работы'
    if form.limits.grades:
        allowed = {str(g) for g in form.limits.grades}
        wrong = [m.full_name for m in participants if m.grade and m.grade not in allowed]
        if wrong:
            errors['members'] = f'Участвовать могут ученики {", ".join(sorted(allowed))} классов: проверьте {wrong[0]}'

    accepted = {(c.key, c.version) for c in app.consents}
    for consent in form.consents:
        if consent.required and (consent.key, consent.version) not in accepted:
            errors[f'consent:{consent.key}'] = 'Нужно согласие'

    others = select(Application.id).where(
        Application.event_id == event.id, Application.id != app.id, Application.status.in_(ACTIVE)
    )
    if form.limits.per_direction and app.direction_id:
        taken = await session.scalar(
            select(func.count()).select_from(others.where(Application.direction_id == app.direction_id).subquery())
        )
        if taken >= form.limits.per_direction:
            errors['direction_id'] = 'В этом направлении больше нет мест'
    if form.limits.per_supervisor:
        for supervisor in supervisors:
            match = [ApplicationMember.full_name == supervisor.full_name]
            if supervisor.email:
                match.append(func.lower(ApplicationMember.email) == supervisor.email.lower())
            taken = await session.scalar(
                select(func.count(func.distinct(ApplicationMember.application_id))).where(
                    ApplicationMember.role == 'supervisor',
                    ApplicationMember.application_id.in_(others),
                    or_(*match),
                )
            )
            if taken >= form.limits.per_supervisor:
                errors['members'] = f'У руководителя {supervisor.full_name} уже максимум заявок'
    return errors


async def submit(session: AsyncSession, app: Application, user: User, queue: Queue) -> None:
    """Отправить заполненную анкету на рассмотрение."""
    if not can_edit(app):
        raise ApplicationError('Эту заявку сейчас нельзя отправить')
    errors = await validate_for_submit(session, app)
    if errors:
        raise ApplicationError('Заявка заполнена не полностью', errors)
    app.status = SUBMITTED
    app.submitted_at = now_utc()
    record(session, 'application.submit', 'application', app.id, user.id)
    await session.flush()
    await notify(queue, app, 'Заявка отправлена', f'Заявка №{app.number} отправлена и ждёт рассмотрения.')


async def withdraw(session: AsyncSession, app: Application, user: User) -> None:
    """Заявитель отзывает заявку, пока по ней нет итогового решения."""
    if app.status not in EDITABLE | {REQUESTED, SUBMITTED}:
        raise ApplicationError('Эту заявку нельзя отозвать')
    app.status = WITHDRAWN
    record(session, 'application.withdraw', 'application', app.id, user.id)
    await session.flush()


# --- Список для оргкомитета ------------------------------------------------------------------


async def list_for_event(
    session: AsyncSession,
    event: Event,
    status: str = '',
    direction_id: int | None = None,
    search: str = '',
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Application], int, dict[str, int]]:
    """Страница заявок мероприятия, общее число по фильтру и счётчики по статусам."""
    base = select(Application).where(Application.event_id == event.id)
    if status:
        base = base.where(Application.status == status)
    if direction_id:
        base = base.where(Application.direction_id == direction_id)
    if search:
        pattern = f'%{search.strip()}%'
        member_match = select(ApplicationMember.application_id).where(ApplicationMember.full_name.ilike(pattern))
        base = base.where(
            or_(
                Application.title.ilike(pattern),
                Application.contact_name.ilike(pattern),
                Application.contact_email.ilike(pattern),
                Application.id.in_(member_match),
            )
        )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(base.order_by(Application.number).offset(offset).limit(limit))
    counts = dict(
        (
            await session.execute(
                select(Application.status, func.count())
                .where(Application.event_id == event.id)
                .group_by(Application.status)
            )
        ).all()
    )
    return list(rows.unique()), total or 0, counts
