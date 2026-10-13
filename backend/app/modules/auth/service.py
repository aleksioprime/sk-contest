from datetime import timedelta
from urllib.parse import quote

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.queue import Queue
from app.core.redis import hit_limit
from app.core.security import create_access_token, hash_secret, new_secret, now_utc
from app.modules.audit.service import record
from app.modules.auth.models import AuthSession, MagicLinkToken
from app.modules.people.models import User
from app.modules.people.service import find_or_create_user_by_email, normalize_email


class AuthError(Exception):
    pass


class RateLimited(AuthError):
    pass


def safe_next_path(value: str | None) -> str:
    """Разрешаем только относительные пути внутри приложения, чтобы ссылка не уводила на чужой сайт."""
    if not value or not value.startswith('/') or value.startswith('//') or '\\' in value:
        return '/'
    return value[:500]


# --- Вход по ссылке из письма ---------------------------------------------------------------


async def request_magic_link(
    session: AsyncSession, redis: Redis, queue: Queue, email: str, next_path: str | None = None
) -> None:
    email = normalize_email(email)
    if await hit_limit(redis, f'magic:{email}', settings.auth.magic_link_per_hour, 3600):
        raise RateLimited('Слишком много запросов. Попробуйте через час.')

    token = new_secret()
    session.add(
        MagicLinkToken(
            email=email,
            token_hash=hash_secret(token),
            next_path=safe_next_path(next_path),
            expires_at=now_utc() + timedelta(minutes=settings.auth.magic_link_ttl_minutes),
        )
    )
    await session.flush()

    link = f'{settings.app_url.rstrip("/")}/auth/magic?token={quote(token)}'
    minutes = settings.auth.magic_link_ttl_minutes
    text = (
        'Здравствуйте!\n\n'
        f'Чтобы войти в SK Events, откройте ссылку:\n{link}\n\n'
        f'Ссылка действует {minutes} минут и подходит для одного входа.\n'
        'Если вы не запрашивали вход, просто удалите это письмо.'
    )
    html = (
        '<p>Здравствуйте!</p>'
        f'<p><a href="{link}" style="display:inline-block;padding:12px 20px;background:#6d28d9;color:#fff;'
        'border-radius:10px;text-decoration:none;font-weight:600">Войти в SK Events</a></p>'
        f'<p>Ссылка действует {minutes} минут и подходит для одного входа.</p>'
        '<p style="color:#666">Если вы не запрашивали вход, просто удалите это письмо.</p>'
    )
    await queue.enqueue('send_email', email, 'Вход в SK Events', text, html)


async def consume_magic_link(session: AsyncSession, token: str) -> tuple[User, str]:
    record_ = await session.scalar(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == hash_secret(token)).with_for_update()
    )
    if record_ is None or record_.used_at is not None or record_.expires_at < now_utc():
        raise AuthError('Ссылка недействительна или уже использована. Запросите новую.')
    record_.used_at = now_utc()
    user = await find_or_create_user_by_email(session, record_.email)
    return user, record_.next_path or '/'


# --- Сессии ---------------------------------------------------------------------------------


async def open_session(
    session: AsyncSession, user: User, method: str, user_agent: str | None, ip: str | None
) -> tuple[str, str]:
    if not user.is_active:
        raise AuthError('Учётная запись отключена. Обратитесь к организаторам.')
    refresh = new_secret()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_hash=hash_secret(refresh),
        method=method,
        user_agent=(user_agent or '')[:500] or None,
        ip=ip,
        expires_at=now_utc() + timedelta(days=settings.auth.refresh_ttl_days),
    )
    session.add(auth_session)
    user.last_login_at = now_utc()
    await session.flush()
    record(session, 'auth.login', 'user', user.id, user.id, method=method)
    return create_access_token(user.id, auth_session.id), refresh


async def refresh_session(session: AsyncSession, refresh: str) -> tuple[str, str]:
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.refresh_hash == hash_secret(refresh)).with_for_update()
    )
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at < now_utc():
        raise AuthError('Сессия завершена. Войдите снова.')
    user = await session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        raise AuthError('Учётная запись отключена.')
    new_refresh = new_secret()
    auth_session.refresh_hash = hash_secret(new_refresh)
    auth_session.last_used_at = now_utc()
    return create_access_token(user.id, auth_session.id), new_refresh


async def close_session(session: AsyncSession, refresh: str | None) -> None:
    if not refresh:
        return
    await session.execute(
        update(AuthSession)
        .where(AuthSession.refresh_hash == hash_secret(refresh), AuthSession.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
