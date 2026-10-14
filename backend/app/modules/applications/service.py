from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.queue import Queue
from app.core.security import now_utc
from app.modules.applications import form as forms
from app.modules.applications.models import (
    ACTIVE,
    DECISIONS,
    DRAFT,
    EDITABLE,
    NEEDS_CHANGES,
    REJECTED,
    SUBMITTED,
    WITHDRAWN,
    Application,
    ApplicationConsent,
    ApplicationFile,
    ApplicationMember,
)
from app.modules.applications.schemas import ApplicationSave
from app.modules.audit.service import record
from app.modules.events.models import Event
from app.modules.events.service import registration_open
from app.modules.files.models import StoredFile
from app.modules.people.models import User

STATUS_TITLES = {
    DRAFT: 'черновик',
    SUBMITTED: 'на рассмотрении',
    NEEDS_CHANGES: 'нужны правки',
    'accepted': 'принята',
    REJECTED: 'отклонена',
    WITHDRAWN: 'отозвана',
}


class ApplicationError(Exception):
    def __init__(self, message: str, errors: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


def event_form(event: Event) -> forms.ApplicationForm:
    return forms.parse_form(event.application_form or forms.default_form(event.type))


def can_edit(app: Application) -> bool:
    if app.status == NEEDS_CHANGES:
        return True
    return app.status == DRAFT and registration_open(app.event)


# --- Заявитель -------------------------------------------------------------------------------


async def create_draft(session: AsyncSession, event: Event, user: User) -> Application:
    if not registration_open(event):
        raise ApplicationError('Приём заявок сейчас закрыт')
    locked = await session.scalar(select(Event.id).where(Event.id == event.id).with_for_update())
    number = (await session.scalar(select(func.max(Application.number)).where(Application.event_id == locked))) or 0
    app = Application(event_id=event.id, number=number + 1, user_id=user.id, members=[], consents=[], files=[])
    person = user.person
    if person and person.full_name:
        role = 'supervisor' if person.is_employee and not person.is_student else 'participant'
        app.members.append(
            ApplicationMember(
                role=role,
                person_id=person.id,
                full_name=person.full_name,
                email=person.email or user.email,
                grade=str(person.study_class.grade or '') if person.study_class else '',
                organization='' if person.source == 'skolstream' else (person.organization or ''),
            )
        )
    session.add(app)
    await session.flush()
    record(session, 'application.create', 'application', app.id, user.id, event_id=event.id)
    return app


async def save(session: AsyncSession, app: Application, user: User, data: ApplicationSave, ip: str | None) -> None:
    if not can_edit(app):
        raise ApplicationError('Эту заявку сейчас нельзя изменить')
    event = app.event
    form = event_form(event)

    answers, errors = forms.clean_answers(form, data.answers)
    if data.direction_id is not None and data.direction_id not in {d.id for d in event.directions}:
        errors['direction_id'] = 'Выберите направление из списка'
    if data.participation_form_id is not None and data.participation_form_id not in {
        f.id for f in event.participation_forms
    }:
        errors['participation_form_id'] = 'Выберите форму участия из списка'

    participants = [m for m in data.members if m.role == 'participant']
    supervisors = [m for m in data.members if m.role == 'supervisor']
    max_participants = form.team.max if form.team.enabled else 1
    if len(participants) > max_participants:
        errors['members'] = f'Участников не может быть больше {max_participants}'
    if len(supervisors) > form.team.supervisors_max:
        errors['members'] = f'Руководителей не может быть больше {form.team.supervisors_max}'

    file_ids = {key: value for key, value in answers.items() if form_field_type(form, key) == 'file' and value}
    if file_ids:
        owned = set(
            await session.scalars(
                select(StoredFile.id).where(StoredFile.id.in_(file_ids.values()), StoredFile.owner_id == user.id)
            )
        )
        for key, file_id in file_ids.items():
            if file_id not in owned:
                errors[key] = 'Файл не найден, загрузите его заново'
    if errors:
        raise ApplicationError('Проверьте правильность заполнения', errors)

    app.title = data.title.strip()
    app.direction_id = data.direction_id
    app.participation_form_id = data.participation_form_id
    app.answers = answers
    app.members = [ApplicationMember(**m.model_dump(), order=i) for i, m in enumerate(data.members)]
    app.files = [ApplicationFile(file_id=file_id, field_key=key) for key, file_id in file_ids.items()]

    accepted = set(data.consents)
    kept = [c for c in app.consents if c.key in accepted]
    for consent in form.consents:
        current = next((c for c in kept if c.key == consent.key), None)
        if consent.key in accepted and (current is None or current.version != consent.version):
            if current:
                kept.remove(current)
            kept.append(
                ApplicationConsent(
                    key=consent.key,
                    version=consent.version,
                    title=consent.title,
                    user_id=user.id,
                    ip=ip,
                    accepted_at=now_utc(),
                )
            )
    app.consents = kept
    await session.flush()


def form_field_type(form: forms.ApplicationForm, key: str) -> str | None:
    return next((f.type for f in form.fields if f.key == key), None)


async def validate_for_submit(session: AsyncSession, app: Application) -> dict[str, str]:
    event = app.event
    form = event_form(event)
    errors = forms.required_errors(form, app.answers)
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
    if not can_edit(app):
        raise ApplicationError('Эту заявку сейчас нельзя отправить')
    errors = await validate_for_submit(session, app)
    if errors:
        raise ApplicationError('Заявка заполнена не полностью', errors)
    app.status = SUBMITTED
    app.submitted_at = now_utc()
    record(session, 'application.submit', 'application', app.id, user.id)
    await session.flush()
    await _notify(queue, app, 'Заявка отправлена', f'Заявка №{app.number} отправлена и ждёт рассмотрения.')


async def withdraw(session: AsyncSession, app: Application, user: User) -> None:
    if app.status not in EDITABLE | {SUBMITTED}:
        raise ApplicationError('Эту заявку нельзя отозвать')
    app.status = WITHDRAWN
    record(session, 'application.withdraw', 'application', app.id, user.id)
    await session.flush()


# --- Модерация -------------------------------------------------------------------------------


async def decide(session: AsyncSession, app: Application, actor: User, status: str, comment: str, queue: Queue) -> None:
    if status not in DECISIONS or app.status in {DRAFT, WITHDRAWN} or app.status == status:
        raise ApplicationError(f'Заявку №{app.number} нельзя перевести в этот статус')
    if status in {NEEDS_CHANGES, REJECTED} and not comment.strip():
        raise ApplicationError('Напишите комментарий для участника', {'comment': 'Заполните поле'})
    record(session, 'application.decide', 'application', app.id, actor.id, old=app.status, new=status)
    app.status = status
    app.moderator_comment = comment.strip()
    app.decided_at = now_utc()
    app.decided_by_id = actor.id
    await session.flush()
    if status != SUBMITTED:
        text = f'Статус заявки №{app.number}: {STATUS_TITLES[status]}.'
        if app.moderator_comment:
            text += f'\n\nКомментарий организаторов:\n{app.moderator_comment}'
        if status == NEEDS_CHANGES:
            text += '\n\nВнесите правки и отправьте заявку повторно.'
        await _notify(queue, app, f'Заявка {STATUS_TITLES[status]}', text)


async def list_for_event(
    session: AsyncSession,
    event: Event,
    status: str = '',
    direction_id: int | None = None,
    search: str = '',
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Application], int, dict[str, int]]:
    base = select(Application).where(Application.event_id == event.id, Application.status != DRAFT)
    if status:
        base = base.where(Application.status == status)
    if direction_id:
        base = base.where(Application.direction_id == direction_id)
    if search:
        pattern = f'%{search.strip()}%'
        member_match = select(ApplicationMember.application_id).where(ApplicationMember.full_name.ilike(pattern))
        base = base.where(or_(Application.title.ilike(pattern), Application.id.in_(member_match)))
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(base.order_by(Application.number).offset(offset).limit(limit))
    counts = dict(
        (
            await session.execute(
                select(Application.status, func.count())
                .where(Application.event_id == event.id, Application.status != DRAFT)
                .group_by(Application.status)
            )
        ).all()
    )
    return list(rows.unique()), total or 0, counts


async def _notify(queue: Queue, app: Application, subject: str, body: str) -> None:
    link = f'{settings.app_url.rstrip("/")}/my/applications/{app.id}'
    text = f'Здравствуйте!\n\n{body}\n\nМероприятие: {app.event.title}\nЗаявка: {link}'
    await queue.enqueue('send_email', app.user.email, f'{subject} · {app.event.title}', text)
