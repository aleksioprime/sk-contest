"""Схемы мероприятий, их направлений, этапов, форм участия и команды."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.events.templates import FORMATS, LEVELS, MODULES, ROLES, STATUSES

SLUG_PATTERN = r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'


class ORMModel(BaseModel):
    """Базовая схема для ответов, создаваемых из ORM-объектов."""

    model_config = ConfigDict(from_attributes=True)


class EventTypeOut(BaseModel):
    """Тип мероприятия: описание и набор включаемых модулей."""

    id: str
    title: str
    description: str
    modules: dict[str, bool]


class DirectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)


class DirectionOut(ORMModel, DirectionIn):
    id: int
    order: int


class StageIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: str = Field(default='onsite', pattern='^(remote|onsite)$')
    description: str = Field(default='', max_length=5000)
    date_start: date | None = None
    date_end: date | None = None

    @model_validator(mode='after')
    def _dates(self):
        """Проверяет, что этап не заканчивается раньше начала."""
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValueError('Дата окончания этапа раньше даты начала')
        return self


class StageOut(ORMModel, StageIn):
    id: int
    order: int


class FormIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class FormOut(ORMModel, FormIn):
    id: int
    order: int


class Reorder(BaseModel):
    """Новый порядок элементов: список их id."""

    ids: list[int]


class MemberIn(BaseModel):
    email: EmailStr
    role: str

    @field_validator('role')
    @classmethod
    def _role(cls, value: str) -> str:
        """Проверяет, что роль известна."""
        if value not in ROLES:
            raise ValueError('Неизвестная роль')
        return value


class MemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: str
    role: str


class EventCreate(BaseModel):
    """Создание мероприятия; copy_from_id указывает мероприятие-образец."""

    type: str
    title: str = Field(min_length=3, max_length=200)
    slug: str = Field(pattern=SLUG_PATTERN)
    copy_from_id: int | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN)
    short_description: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    level: str | None = None
    format: str | None = None
    place: str | None = Field(default=None, max_length=300)
    date_start: date | None = None
    date_end: date | None = None
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    details_closes_at: datetime | None = None
    academic_year_id: int | None = None
    cover_file_id: int | None = None
    modules: dict[str, bool] | None = None

    @field_validator('level')
    @classmethod
    def _level(cls, value):
        """Проверяет, что уровень известен."""
        if value is not None and value not in LEVELS:
            raise ValueError('Неизвестный уровень')
        return value

    @field_validator('format')
    @classmethod
    def _format(cls, value):
        """Проверяет, что формат известен."""
        if value is not None and value not in FORMATS:
            raise ValueError('Неизвестный формат')
        return value

    @field_validator('modules')
    @classmethod
    def _modules(cls, value):
        """Проверяет, что названия модулей известны."""
        if value is not None and set(value) - set(MODULES):
            raise ValueError('Неизвестный модуль')
        return value


class StatusChange(BaseModel):
    status: str

    @field_validator('status')
    @classmethod
    def _status(cls, value):
        """Проверяет, что статус известен."""
        if value not in STATUSES:
            raise ValueError('Неизвестный статус')
        return value


class EventListItem(BaseModel):
    """Мероприятие в списке с ролями пользователя."""

    id: int
    slug: str
    type: str
    title: str
    status: str
    date_start: date | None
    date_end: date | None
    my_roles: list[str]


class EventOut(ORMModel):
    id: int
    slug: str
    type: str
    title: str
    short_description: str
    description: str
    status: str
    level: str
    format: str
    place: str
    date_start: date | None
    date_end: date | None
    registration_opens_at: datetime | None
    registration_closes_at: datetime | None
    details_closes_at: datetime | None
    academic_year_id: int | None
    cover_file_id: int | None
    modules: dict[str, bool]
    directions: list[DirectionOut]
    stages: list[StageOut]
    participation_forms: list[FormOut]
    allowed_statuses: list[str] = []
    my_roles: list[str] = []
    can_manage: bool = False
