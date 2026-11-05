"""Письма заявителю: статус заявки и приглашение в личный кабинет."""

from html import escape
from urllib.parse import quote

from sk_common.auth.service import issue_personal_login
from sk_common.queue import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.letters import app_link, button, can_email
from app.modules.applications.models import Application

INVITE_PURPOSE = 'invite'
INVITE_TTL_MINUTES = 7 * 24 * 60


async def notify(queue: Queue, app: Application, subject: str, body: str) -> None:
    """Письмо о заявке. Ссылка на кабинет есть, только если заявка уже связана с учётной записью."""
    email = app.applicant_email
    if not can_email(email):
        return
    text = f'Здравствуйте!\n\n{body}\n\nМероприятие: {app.event.title}'
    if app.user_id:
        text += f'\nЗаявка: {app_link(f"/my/applications/{app.id}")}'
    await queue.enqueue('send_email', email, f'{subject} · {app.event.title}', text)


async def send_invitation(session: AsyncSession, queue: Queue, app: Application) -> bool:
    """Приглашение дописать заявку: одноразовая ссылка сразу открывает её в кабинете. False — нет адреса для письма."""
    if not can_email(app.applicant_email):
        return False
    path = f'/my/applications/{app.id}'
    token, _ = await issue_personal_login(session, app.user, path, INVITE_PURPOSE, INVITE_TTL_MINUTES)
    link = app_link(f'/auth/magic?token={quote(token)}')
    event = app.event
    text = (
        'Здравствуйте!\n\n'
        f'Организаторы подтвердили вашу заявку №{app.number} на «{event.title}».\n'
        'Заполните оставшиеся поля в личном кабинете: сведения о работе, руководителей, описание и файлы.\n\n'
        f'Открыть заявку: {link}\n\n'
        'Ссылка действует 7 дней и подходит для одного входа. Позже можно войти на сайте по этому адресу.'
    )
    html = (
        f'<p>Здравствуйте!</p><p>Организаторы подтвердили вашу заявку №{app.number} на «{escape(event.title)}».</p>'
        '<p>Заполните оставшиеся поля в личном кабинете: сведения о работе, руководителей, описание и файлы.</p>'
        + button(link, 'Заполнить заявку')
        + '<p style="color:#666">Ссылка действует 7 дней и подходит для одного входа. '
        'Позже можно войти на сайте по этому адресу.</p>'
    )
    await queue.enqueue('send_email', app.applicant_email, f'Заявка подтверждена · {event.title}', text, html)
    return True
