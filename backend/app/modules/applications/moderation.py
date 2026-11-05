"""Работа модератора: решения по заявкам, подтверждение общей заявки и связь с человеком из базы."""

from sk_common.audit import record
from sk_common.people.models import Person, User
from sk_common.people.service import ensure_user, find_or_create_user_by_email, set_full_name
from sk_common.queue import Queue
from sk_common.security import now_utc
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.letters import can_email
from app.modules.applications.models import (
    ACCEPTED,
    DRAFT,
    NEEDS_CHANGES,
    REJECTED,
    REQUESTED,
    SUBMITTED,
    Application,
    ApplicationMember,
)
from app.modules.applications.notifications import notify, send_invitation
from app.modules.applications.schemas import ContactIn, PersonMatch
from app.modules.applications.service import STATUS_TITLES, ApplicationError, event_form

CONFIRMED = 'confirmed'  # решение «подтвердить общую заявку»; статус станет draft или accepted
SEARCH_LIMIT = 20


def allowed_decisions(app: Application) -> list[str]:
    """Какие решения доступны модератору при текущем статусе заявки."""
    match app.status:
        case 'requested':
            return [CONFIRMED, REJECTED]
        case 'draft':
            return [REJECTED]
        case 'withdrawn':
            return []
        case 'rejected' if app.confirmed_at is None:
            return [REQUESTED]  # отклонена на первом шаге
        case 'rejected' if app.submitted_at is None:
            return [DRAFT]  # отклонена, пока участник заполнял анкету
    return [s for s in (ACCEPTED, NEEDS_CHANGES, REJECTED, SUBMITTED) if s != app.status]


async def decide(session: AsyncSession, app: Application, actor: User, status: str, comment: str, queue: Queue) -> None:
    """Применить решение модератора и сообщить заявителю."""
    if status not in allowed_decisions(app):
        raise ApplicationError(f'Заявку №{app.number} нельзя перевести в этот статус')
    if status in {NEEDS_CHANGES, REJECTED} and not comment.strip():
        raise ApplicationError('Напишите комментарий для участника', {'comment': 'Заполните поле'})
    if status == CONFIRMED:
        await _confirm(session, app, actor, comment, queue)
        return
    record(session, 'application.decide', 'application', app.id, actor.id, old=app.status, new=status)
    app.status = status
    app.moderator_comment = comment.strip()
    app.decided_at = now_utc()
    app.decided_by_id = actor.id
    await session.flush()
    if status not in {SUBMITTED, REQUESTED, DRAFT}:
        text = f'Статус заявки №{app.number}: {STATUS_TITLES[status]}.'
        if app.moderator_comment:
            text += f'\n\nКомментарий организаторов:\n{app.moderator_comment}'
        if status == NEEDS_CHANGES:
            text += '\n\nВнесите правки и отправьте заявку повторно.'
        await notify(queue, app, f'Заявка {STATUS_TITLES[status]}', text)


# --- Подтверждение общей заявки --------------------------------------------------------------


async def _confirm(session: AsyncSession, app: Application, actor: User, comment: str, queue: Queue) -> None:
    """Заявка получает учётную запись и участника: дальше её дописывают в кабинете или она сразу принята."""
    user = await _ensure_applicant(session, app)
    details_step = event_form(app.event).registration.details_step
    now = now_utc()
    record(session, 'application.confirm', 'application', app.id, actor.id, user_id=user.id)
    if not app.members:
        app.members = [_applicant_member(app, user)]
    app.status = DRAFT if details_step else ACCEPTED
    app.confirmed_at = now
    app.moderator_comment = comment.strip()
    app.decided_at = now
    app.decided_by_id = actor.id
    if not details_step:
        app.submitted_at = now
    await session.flush()
    await session.refresh(app, ['user'])
    if details_step:
        await send_invitation(session, queue, app)
    else:
        await notify(queue, app, 'Заявка принята', f'Заявка №{app.number} принята. До встречи на мероприятии!')


async def _ensure_applicant(session: AsyncSession, app: Application) -> User:
    """Учётная запись заявителя: уже связанная или найденная и созданная по контактному email."""
    if app.user_id:
        return await session.get(User, app.user_id)
    if not can_email(app.contact_email):
        raise ApplicationError('В заявке нет email: укажите его или свяжите заявку с человеком из базы')
    user = await find_or_create_user_by_email(session, app.contact_email)
    if app.contact_name and not (user.person and user.person.full_name):
        await set_full_name(session, user, app.contact_name)
    person = user.person
    if person and person.is_external and app.contact_organization and not person.organization:
        person.organization = app.contact_organization[:255]
    app.user_id = user.id
    return user


def _applicant_member(app: Application, user: User) -> ApplicationMember:
    """Запись заявителя в составе заявки. Сотрудник гимназии считается руководителем, остальные — участниками."""
    person = user.person
    study_class = person.study_class if person else None
    is_supervisor = bool(person and person.is_employee and not person.is_student)
    return ApplicationMember(
        role='supervisor' if is_supervisor else 'participant',
        person_id=person.id if person else None,
        full_name=(person.full_name if person else '') or app.contact_name or user.email,
        email=app.applicant_email if can_email(app.applicant_email) else '',
        grade=str(study_class.grade or '') if study_class else app.contact_grade,
        organization='' if person and not person.is_external else app.contact_organization,
    )


async def resend_invitation(session: AsyncSession, app: Application, actor: User, queue: Queue) -> None:
    """Новая ссылка, если письмо потерялось или ссылка устарела."""
    if app.status != DRAFT:
        raise ApplicationError('Приглашение отправляется только для заявок, которые заполняет участник')
    if not await send_invitation(session, queue, app):
        raise ApplicationError('У этого человека нет адреса электронной почты')
    record(session, 'application.invite', 'application', app.id, actor.id)


async def update_contact(session: AsyncSession, app: Application, actor: User, data: ContactIn) -> None:
    """Правка контактов модератором. Учётную запись и состав заявки это не меняет."""
    app.contact_name = ' '.join(data.name.split())
    app.contact_email = data.email.strip().lower()
    app.contact_phone = data.phone.strip()
    app.contact_organization = data.organization.strip()
    app.contact_grade = data.grade.strip()
    record(session, 'application.contact', 'application', app.id, actor.id)
    await session.flush()


# --- Связь заявки с человеком ----------------------------------------------------------------


def _match(person: Person, user: User | None, by_email: bool = False) -> PersonMatch:
    """Человек из базы в ответе API."""
    email = user.email if user else person.email
    kind = 'student' if person.is_student else 'employee' if person.is_employee else 'external'
    return PersonMatch(
        person_id=person.id,
        full_name=person.full_name or email or '',
        email=email if can_email(email) else None,
        kind=kind,
        class_name=person.study_class.name if person.study_class else '',
        has_account=user is not None,
        by_email=by_email,
    )


def _people_query():
    """Активные люди вместе с учётными записями, если они есть."""
    return (
        select(Person, User)
        .outerjoin(User, User.person_id == Person.id)
        .where(Person.is_active.is_(True))
        .order_by(Person.last_name, Person.first_name, Person.id)
    )


def _word_filter(word: str):
    """Слово запроса встречается в ФИО или адресе."""
    pattern = f'%{word}%'
    return or_(
        Person.last_name.ilike(pattern),
        Person.first_name.ilike(pattern),
        Person.middle_name.ilike(pattern),
        Person.email.ilike(pattern),
        User.email.ilike(pattern),
    )


async def search_people(session: AsyncSession, query: str) -> list[PersonMatch]:
    """Поиск по ФИО и email: должны совпасть все слова запроса."""
    words = query.split()
    if not words or len(query.strip()) < 2:
        return []
    rows = await session.execute(_people_query().where(*[_word_filter(word) for word in words]).limit(SEARCH_LIMIT))
    return [_match(person, user) for person, user in rows.unique().all()]


async def find_matches(session: AsyncSession, app: Application) -> list[PersonMatch]:
    """Кто в базе похож на заявителя: сначала совпадение по email, затем по фамилии и имени."""
    result: dict[int, PersonMatch] = {}
    email = app.contact_email.strip().lower()
    if email:
        condition = or_(func.lower(Person.email) == email, User.email == email)
        for person, user in (await session.execute(_people_query().where(condition))).unique().all():
            result[person.id] = _match(person, user, by_email=True)
    parts = app.contact_name.split()
    if len(parts) >= 2:
        last_name, first_name = func.lower(Person.last_name), func.lower(Person.first_name)
        straight = (last_name == parts[0].lower()) & (first_name == parts[1].lower())
        reversed_ = (last_name == parts[1].lower()) & (first_name == parts[0].lower())
        query = _people_query().where(or_(straight, reversed_)).limit(SEARCH_LIMIT)
        for person, user in (await session.execute(query)).unique().all():
            result.setdefault(person.id, _match(person, user))
    # Человек, с которым заявка уже связана, в подсказках не нужен
    linked_person_id = app.user.person_id if app.user else None
    return [match for person_id, match in result.items() if person_id != linked_person_id]


async def link_person(session: AsyncSession, app: Application, actor: User, person_id: int) -> None:
    """Присоединить заявку к существующему человеку. У человека без учётной записи она появится."""
    person = await session.get(Person, person_id)
    if person is None or not person.is_active:
        raise ApplicationError('Человек не найден')
    user = await session.scalar(select(User).where(User.person_id == person.id))
    if user is None:
        email = person.email or app.contact_email
        if not email:
            raise ApplicationError('У этого человека нет email: укажите адрес в заявке')
        user = await ensure_user(session, person, email)
        if user.person_id != person.id:
            raise ApplicationError(f'Адрес {email} уже занят другой учётной записью')

    old_person_id = app.user.person_id if app.user else None
    for member in app.members:
        if old_person_id and member.person_id == old_person_id:
            member.person_id = person.id
            member.full_name = person.full_name or member.full_name
    record(session, 'application.link', 'application', app.id, actor.id, old=app.user_id, new=user.id)
    app.user_id = user.id
    await session.flush()
    await session.refresh(app, ['user'])


async def unlink_person(session: AsyncSession, app: Application, actor: User) -> None:
    """Снять связь, пока заявка не подтверждена: при подтверждении человек снова определится по email."""
    if app.status != REQUESTED:
        raise ApplicationError('Связь можно снять только до подтверждения заявки. Позже выберите другого человека.')
    record(session, 'application.unlink', 'application', app.id, actor.id, old=app.user_id)
    app.user_id = None
    await session.flush()
    await session.refresh(app, ['user'])
