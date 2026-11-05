"""Схемы заявок: сохранение, просмотр, списки, решения модерации и открытая регистрация."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class MemberIn(BaseModel):
    role: str = Field(pattern='^(participant|supervisor)$')
    full_name: str = Field(min_length=1, max_length=300)
    email: str = Field(default='', max_length=255)
    grade: str = Field(default='', max_length=20)
    organization: str = Field(default='', max_length=300)


class MemberOut(MemberIn):
    id: int
    person_id: int | None


class ApplicationSave(BaseModel):
    """Данные заявки, которые сохраняет заявитель: ответы формы, участники и принятые согласия."""

    title: str = Field(default='', max_length=300)
    direction_id: int | None = None
    participation_form_id: int | None = None
    answers: dict = {}
    members: list[MemberIn] = []
    consents: list[str] = []


class StaffApplication(ApplicationSave):
    """Заявка, созданная сотрудником вместо заявителя; контактное лицо видит её в кабинете."""

    owner_email: EmailStr | None = Field(default=None, description='Контактное лицо: увидит заявку в кабинете')
    status: str = Field(default='accepted', pattern='^(submitted|accepted)$')


class ContactOut(BaseModel):
    """Контакты заявителя из общей заявки."""

    name: str = Field(default='', max_length=300)
    email: str = Field(default='', max_length=255)
    phone: str = Field(default='', max_length=40)
    organization: str = Field(default='', max_length=300)
    grade: str = Field(default='', max_length=20)


class ContactIn(ContactOut):
    """Правка контактов модератором, например опечатки в адресе."""

    email: EmailStr | Literal[''] = ''


class FileRef(BaseModel):
    id: int
    name: str
    size: int
    url: str
    field_key: str


class ConsentOut(BaseModel):
    key: str
    version: str
    title: str
    accepted_at: datetime


class Ref(BaseModel):
    """Краткая ссылка на справочную запись: id и название."""

    id: int
    title: str


class EventRef(BaseModel):
    id: int
    slug: str
    title: str


class ApplicationOut(BaseModel):
    id: int
    number: int
    event: EventRef
    status: str
    source: str
    title: str
    direction: Ref | None
    participation_form: Ref | None
    answers: dict
    contact: ContactOut
    is_linked: bool
    raw_payload: dict
    members: list[MemberOut]
    consents: list[ConsentOut]
    files: list[FileRef]
    moderator_comment: str
    applicant_email: str
    applicant_name: str
    created_at: datetime
    confirmed_at: datetime | None
    submitted_at: datetime | None
    decided_at: datetime | None
    allowed_decisions: list[str] = []
    can_edit: bool = False
    can_submit: bool = False
    can_withdraw: bool = False
    can_manage: bool = False


class ApplicationListItem(BaseModel):
    id: int
    number: int
    title: str
    status: str
    source: str
    direction: str
    participants: list[str]
    supervisors: list[str]
    applicant_name: str
    applicant_email: str
    is_linked: bool
    created_at: datetime
    submitted_at: datetime | None


class ApplicationPage(BaseModel):
    """Страница списка заявок с общим числом и счётчиками по статусам."""

    items: list[ApplicationListItem]
    total: int
    counts: dict[str, int]


class Decision(BaseModel):
    """confirmed — подтвердить общую заявку; requested и draft — вернуть заявку на её прежний шаг."""

    status: str = Field(pattern='^(confirmed|requested|draft|accepted|needs_changes|rejected|submitted)$')
    comment: str = Field(default='', max_length=5000)


class BulkDecision(Decision):
    """Одно решение, применяемое сразу к нескольким заявкам."""

    ids: list[int] = Field(min_length=1, max_length=500)


class PublicEvent(BaseModel):
    """Мероприятие на странице открытой формы."""

    id: int
    slug: str
    title: str
    short_description: str
    description: str
    place: str
    date_start: date | None
    date_end: date | None
    cover_url: str | None


class PublicForm(BaseModel):
    """Данные открытой формы: мероприятие, анкета, справочники и состояние приёма."""

    event: PublicEvent
    form: dict
    directions: list[Ref]
    participation_forms: list[Ref]
    registration_open: bool
    registration_closes_at: datetime | None


class OpenEvent(BaseModel):
    """Мероприятие с открытым приёмом заявок: список в кабинете."""

    slug: str
    title: str
    short_description: str
    date_start: date | None
    date_end: date | None
    registration_closes_at: datetime | None


class RegistrationIn(BaseModel):
    """Общая заявка: всё, что можно узнать о человеке до подтверждения."""

    full_name: str = Field(default='', max_length=300)
    email: str = Field(default='', max_length=255)
    phone: str = Field(default='', max_length=40)
    organization: str = Field(default='', max_length=300)
    grade: str = Field(default='', max_length=20)
    title: str = Field(default='', max_length=300)
    direction_id: int | None = None
    participation_form_id: int | None = None
    answers: dict = {}
    consents: list[str] = []
    captcha_token: str | None = None


class RegistrationResult(BaseModel):
    """Результат подачи общей заявки."""

    message: str
    application_id: int | None = Field(default=None, description='Только для вошедшего пользователя')


class PersonMatch(BaseModel):
    """Человек из базы для связи с открытой заявкой."""

    person_id: int
    full_name: str
    email: str | None
    kind: str  # student | employee | external
    class_name: str
    has_account: bool
    by_email: bool = False


class LinkPerson(BaseModel):
    """Выбор человека из базы для привязки к открытой заявке."""

    person_id: int


class WebhookOut(BaseModel):
    """Адрес вебхука для приёма заявок из внешней формы."""

    url: str | None
