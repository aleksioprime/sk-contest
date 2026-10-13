from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import session_maker
from app.core.security import TokenError, decode_access_token, now_utc
from app.modules.auth.models import AuthSession
from app.modules.people.models import User


async def get_db() -> AsyncIterator[AsyncSession]:
    """Сессия БД на запрос. Изменения фиксируются явно через session.commit() в обработчике."""
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


Db = Annotated[AsyncSession, Depends(get_db)]


def _access_token(request: Request) -> str | None:
    header = request.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        return header[7:]
    return request.cookies.get(settings.auth.access_cookie)


async def get_optional_user(request: Request, db: Db) -> User | None:
    token = _access_token(request)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except TokenError:
        return None
    active_session = await db.scalar(
        select(AuthSession.id).where(
            AuthSession.id == int(payload['sid']),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now_utc(),
        )
    )
    if active_session is None:
        return None
    user = await db.get(User, int(payload['sub']))
    return user if user and user.is_active else None


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Требуется вход')
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Недостаточно прав')
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]
