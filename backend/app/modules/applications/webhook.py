"""Разбор заявок из внешних форм (Tilda и другие): данные приводятся к общей заявке.

Поля распознаются по настройке организатора (registration.webhook_fields), затем по ключу и подписи
вопроса анкеты, затем по распространённым названиям. Ничего не теряется: исходные данные остаются
в заявке, и модератор видит то, что не удалось разобрать.
"""

from fastapi import Request

from app.modules.applications.form import EMAIL_RE, PHONE_RE, ApplicationForm, FormField, check_value
from app.modules.applications.schemas import RegistrationIn
from app.modules.events.models import Event

MAX_BODY = 64 * 1024
MAX_VALUE = 5000
# Служебные поля внешних форм, которые незачем показывать модератору
IGNORED = {'cookies', 'formname', 'referer'}
ALIASES = {
    'full_name': {'full_name', 'fullname', 'fio', 'name', 'фио', 'имя', 'ваше имя', 'имя и фамилия'},
    'email': {'email', 'e-mail', 'mail', 'почта', 'электронная почта'},
    'phone': {'phone', 'tel', 'telephone', 'телефон'},
    'organization': {'organization', 'school', 'организация', 'школа', 'учебное заведение'},
    'grade': {'grade', 'class', 'класс'},
    'title': {'title', 'work', 'project', 'название', 'название работы', 'тема', 'тема работы'},
    'direction': {'direction', 'section', 'направление', 'секция', 'номинация'},
    'participation_form': {'participation_form', 'форма участия'},
    'external_id': {'tranid', 'external_id', 'submission_id'},
}


async def read_payload(request: Request) -> dict[str, str]:
    """Тело запроса (JSON или форма) как плоский словарь строк."""
    if request.headers.get('content-type', '').startswith('application/json'):
        body = await request.json()
        items = body.items() if isinstance(body, dict) else []
    else:
        items = (await request.form()).multi_items()
    return {str(key): str(value)[:MAX_VALUE] for key, value in items}


def is_test_request(payload: dict[str, str]) -> bool:
    """Tilda проверяет адрес при подключении запросом test=test."""
    return payload.get('test') == 'test'


class _Lookup:
    """Поиск значений во входящих данных без учёта регистра."""

    def __init__(self, payload: dict[str, str], custom: dict[str, str]):
        """Нормализует имена и значения входящих данных и настройки соответствия полей."""
        self.values = {key.strip().lower(): value.strip() for key, value in payload.items()}
        self.custom = {key: name.strip().lower() for key, name in custom.items()}

    def get(self, target: str, *names: str) -> str:
        """Значение поля: сначала по настройке организатора, затем по подходящим именам."""
        if target in self.custom:
            return self.values.get(self.custom[target], '')
        return next((self.values[name] for name in names if self.values.get(name)), '')

    def builtin(self, target: str) -> str:
        """Значение встроенного поля по его стандартным именам."""
        return self.get(target, *ALIASES[target])


def _coerce(field: FormField, raw: str):
    """Значение вопроса анкеты из строки. Неподходящее значение отбрасывается, оно останется в исходных данных."""
    value: object = raw
    match field.type:
        case 'multiselect':
            value = [part.strip() for part in raw.replace(',', ';').split(';') if part.strip()]
        case 'checkbox':
            value = raw.lower() not in {'', '0', 'no', 'false', 'нет', 'off'}
        case 'number':
            try:
                value = float(raw.replace(',', '.'))
            except ValueError:
                return None
    return None if check_value(field, value) else value


def _pick_by_title(items, raw: str) -> int | None:
    """Направление или форма участия по названию из внешней формы."""
    title = raw.lower()
    return next((item.id for item in items if item.title.strip().lower() == title), None)


def parse(event: Event, form: ApplicationForm, payload: dict[str, str]) -> tuple[RegistrationIn, str | None, dict]:
    """Возвращает общую заявку, номер записи во внешней системе и исходные данные для показа модератору."""
    lookup = _Lookup(payload, form.registration.webhook_fields)
    email = lookup.builtin('email').lower()
    phone = lookup.builtin('phone')
    answers = {}
    for field in form.fields:
        if field.type == 'file':
            continue
        raw = lookup.get(field.key, field.key.lower(), field.label.strip().lower())
        if raw and (value := _coerce(field, raw)) is not None:
            answers[field.key] = value
    data = RegistrationIn(
        full_name=lookup.builtin('full_name')[:300],
        email=email if EMAIL_RE.match(email) else '',
        phone=phone[:40] if PHONE_RE.match(phone) else '',
        organization=lookup.builtin('organization')[:300],
        grade=lookup.builtin('grade')[:20],
        title=lookup.builtin('title')[:300],
        direction_id=_pick_by_title(event.directions, lookup.builtin('direction')),
        participation_form_id=_pick_by_title(event.participation_forms, lookup.builtin('participation_form')),
        answers=answers,
    )
    raw_payload = {key: value for key, value in payload.items() if key.strip().lower() not in IGNORED}
    return data, lookup.builtin('external_id')[:100] or None, raw_payload
