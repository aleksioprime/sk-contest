"""Общие части писем: ссылка на приложение, кнопка, время по Москве, проверка адреса."""

from datetime import datetime, timedelta, timezone
from html import escape

from app.core.config import settings

# Служебный домен учётных записей без настоящего адреса (судьи без email)
NO_EMAIL_DOMAIN = 'judges.sk-events.local'
MSK = timezone(timedelta(hours=3))  # время в письмах — московское, как у большинства мероприятий


def app_link(path: str) -> str:
    """Полная ссылка на страницу приложения."""
    return f'{settings.app_url.rstrip("/")}{path}'


def moscow_time(moment: datetime) -> str:
    """Дата и время для текста письма."""
    return moment.astimezone(MSK).strftime('%d.%m.%Y %H:%M') + ' (МСК)'


def button(link: str, title: str) -> str:
    """Кнопка-ссылка для HTML-письма."""
    return (
        f'<p><a href="{link}" style="display:inline-block;padding:12px 20px;background:{settings.brand_color};'
        f'color:#fff;border-radius:10px;text-decoration:none;font-weight:600">{escape(title)}</a></p>'
    )


def can_email(email: str | None) -> bool:
    """Можно ли написать на адрес: не пустой и не служебный."""
    return bool(email) and not email.endswith('@' + NO_EMAIL_DOMAIN)
