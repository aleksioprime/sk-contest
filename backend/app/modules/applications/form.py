"""Анкета заявки: схема, анкета по умолчанию и проверка ответов.

Анкета хранится в events.application_form:
{
  "registration": {"open_form", "details_step", "asked", "intro", "success_text", "webhook_fields"},
  "fields": [{"key", "type", "label", "help", "required", "on_registration", "options", "visible_if": {...}}],
  "team": {"enabled", "min", "max", "supervisors_max", "require_supervisor"},
  "limits": {"per_supervisor", "per_direction", "grades"},
  "consents": [{"key", "title", "text", "version", "required"}]
}
Название работы, направление и форма участия — встроенные поля заявки, в анкете их нет.
ФИО и email спрашиваются всегда, остальные встроенные поля первого шага перечислены в registration.asked.
"""

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

FIELD_TYPES = (
    'text',
    'textarea',
    'select',
    'multiselect',
    'checkbox',
    'number',
    'date',
    'email',
    'phone',
    'url',
    'file',
)
# Встроенные поля, которые можно спросить на первом шаге, кроме обязательных ФИО и email
ASKABLE = ('phone', 'organization', 'grade', 'title', 'direction', 'participation_form')
KEY_RE = r'^[a-z][a-z0-9_]{0,39}$'
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_RE = re.compile(r'^\+?[\d\s()-]{7,20}$')
URL_RE = re.compile(r'^https?://\S+$')

DEFAULT_CONSENT_TEXT = (
    'Я даю согласие Гимназии Сколково на обработку персональных данных, указанных в заявке, '
    'в целях организации и проведения мероприятия и публикации его итогов.'
)


class VisibleIf(BaseModel):
    """Условие показа поля: поле field должно иметь значение equals."""

    field: str
    equals: str | bool | int | None = None


class FormField(BaseModel):
    """Поле анкеты: тип, подпись, обязательность, варианты ответа и условие показа."""

    key: str = Field(pattern=KEY_RE)
    type: str
    label: str = Field(min_length=1, max_length=200)
    help: str = Field(default='', max_length=500)
    required: bool = False
    # Спрашивать уже в общей заявке, а не только в кабинете после подтверждения
    on_registration: bool = False
    options: list[str] = []
    visible_if: VisibleIf | None = None

    @field_validator('type')
    @classmethod
    def _type(cls, value):
        """Проверяет, что тип поля известен."""
        if value not in FIELD_TYPES:
            raise ValueError('Неизвестный тип поля')
        return value

    @model_validator(mode='after')
    def _options(self):
        """Требует варианты ответа для выбора и запрещает файл на этапе общей заявки."""
        if self.type in ('select', 'multiselect') and not self.options:
            raise ValueError(f'У поля «{self.label}» нет вариантов ответа')
        if self.type == 'file' and self.on_registration:
            raise ValueError(f'Файл «{self.label}» можно загрузить только в кабинете, после подтверждения заявки')
        return self


class TeamSettings(BaseModel):
    """Настройки команды: размер и число руководителей."""

    enabled: bool = False
    min: int = Field(default=1, ge=1, le=50)
    max: int = Field(default=1, ge=1, le=50)
    supervisors_max: int = Field(default=2, ge=0, le=10)
    require_supervisor: bool = False

    @model_validator(mode='after')
    def _range(self):
        """Проверяет, что максимальный размер команды не меньше минимального."""
        if self.max < self.min:
            raise ValueError('Максимальный размер команды меньше минимального')
        return self


class Limits(BaseModel):
    """Ограничения приёма: число заявок на руководителя и на направление, допустимые классы."""

    per_supervisor: int | None = Field(default=None, ge=1)
    per_direction: int | None = Field(default=None, ge=1)
    grades: list[int] | None = None


class Consent(BaseModel):
    """Согласие, которое заявитель принимает при подаче заявки; version фиксирует редакцию текста."""

    key: str = Field(pattern=KEY_RE)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=5000)
    version: str = Field(default='1', max_length=20)
    required: bool = True


class RegistrationSettings(BaseModel):
    """Первый шаг: общая заявка через открытую форму или вебхук."""

    open_form: bool = True  # принимать заявки без входа; иначе форма доступна только вошедшим
    details_step: bool = True  # после подтверждения участник дописывает анкету; иначе заявка сразу принята
    asked: list[str] = ['phone', 'organization', 'grade']
    intro: str = Field(default='', max_length=2000)
    success_text: str = Field(default='', max_length=1000)
    # Наше поле → имя поля во внешней форме, если оно не распознаётся автоматически (см. webhook.py)
    webhook_fields: dict[str, str] = {}

    @field_validator('asked')
    @classmethod
    def _asked(cls, value):
        """Проверяет, что в первом шаге спрашиваются только допустимые поля."""
        if set(value) - set(ASKABLE):
            raise ValueError('Неизвестное поле первого шага')
        return value


class ApplicationForm(BaseModel):
    """Анкета мероприятия: поля, команда, ограничения и согласия."""

    registration: RegistrationSettings = RegistrationSettings()
    fields: list[FormField] = []
    team: TeamSettings = TeamSettings()
    limits: Limits = Limits()
    consents: list[Consent] = []

    @model_validator(mode='after')
    def _keys(self):
        """Проверяет уникальность ключей полей и согласий и существование полей в условиях показа."""
        keys = [f.key for f in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError('Ключи полей анкеты должны быть уникальными')
        for field in self.fields:
            if field.visible_if and field.visible_if.field not in keys:
                raise ValueError(f'Поле «{field.label}» зависит от несуществующего поля')
        consent_keys = [c.key for c in self.consents]
        if len(consent_keys) != len(set(consent_keys)):
            raise ValueError('Ключи согласий должны быть уникальными')
        return self


def default_form(event_type: str) -> dict:
    """Анкета по умолчанию. На открытое событие хватает общей заявки, второго шага у него нет."""
    team = event_type in ('project_contest', 'creative')
    fields = [
        FormField(key='annotation', type='textarea', label='Краткое описание работы', required=True),
        FormField(key='work', type='file', label='Файл работы', help='PDF, презентация или документ до 25 МБ'),
    ]
    if event_type == 'open_event':
        fields = []
    form = ApplicationForm(
        registration=RegistrationSettings(details_step=event_type != 'open_event'),
        fields=fields,
        team=TeamSettings(
            enabled=team, min=1, max=3 if team else 1, require_supervisor=event_type == 'project_contest'
        ),
        consents=[
            Consent(key='personal_data', title='Согласие на обработку персональных данных', text=DEFAULT_CONSENT_TEXT)
        ],
    )
    return form.model_dump()


def parse_form(raw: dict | None) -> ApplicationForm:
    """Анкета из JSON мероприятия с подстановкой значений по умолчанию."""
    return ApplicationForm.model_validate(raw or {})


# --- Проверка ответов ------------------------------------------------------------------------


def visible_fields(fields: list[FormField], answers: dict) -> list[FormField]:
    """Поля, которые видит заявитель при текущих ответах (условие visible_if)."""
    result = []
    for field in fields:
        condition = field.visible_if
        if condition is None:
            result.append(field)
            continue
        value = answers.get(condition.field)
        shown = value == condition.equals or (isinstance(value, list) and condition.equals in value)
        if shown:
            result.append(field)
    return result


def _empty(value) -> bool:
    """Пусто ли значение ответа: нет значения, пустая строка, пустой список или False."""
    return value is None or value == '' or value == [] or value is False


def check_value(field: FormField, value) -> str | None:
    """Ошибка значения поля или None. Пустые значения проверяются отдельно (required)."""
    if _empty(value):
        return None
    match field.type:
        case 'text' | 'textarea':
            if not isinstance(value, str) or len(value) > (500 if field.type == 'text' else 10000):
                return 'Слишком длинный текст'
        case 'select':
            if value not in field.options:
                return 'Выберите вариант из списка'
        case 'multiselect':
            if not isinstance(value, list) or any(v not in field.options for v in value):
                return 'Выберите варианты из списка'
        case 'checkbox':
            if not isinstance(value, bool):
                return 'Ожидается отметка'
        case 'number':
            if isinstance(value, bool) or not isinstance(value, int | float):
                return 'Введите число'
        case 'date':
            try:
                date.fromisoformat(str(value))
            except ValueError:
                return 'Введите дату'
        case 'email':
            if not EMAIL_RE.match(str(value)):
                return 'Введите адрес электронной почты'
        case 'phone':
            if not PHONE_RE.match(str(value)):
                return 'Введите номер телефона'
        case 'url':
            if not URL_RE.match(str(value)):
                return 'Ссылка должна начинаться с http:// или https://'
        case 'file':
            if not isinstance(value, int):
                return 'Загрузите файл'
    return None


def clean_answers(form: ApplicationForm, answers: dict) -> tuple[dict, dict[str, str]]:
    """Оставляет только известные поля и проверяет формат. Возвращает (ответы, ошибки по ключам)."""
    known = {f.key: f for f in form.fields}
    cleaned, errors = {}, {}
    for key, value in (answers or {}).items():
        field = known.get(key)
        if field is None:
            continue
        error = check_value(field, value)
        if error:
            errors[key] = error
        cleaned[key] = value
    return cleaned, errors


def required_errors(fields: list[FormField], answers: dict) -> dict[str, str]:
    """Незаполненные обязательные поля среди видимых."""
    return {
        field.key: 'Заполните поле'
        for field in visible_fields(fields, answers)
        if field.required and _empty(answers.get(field.key))
    }
