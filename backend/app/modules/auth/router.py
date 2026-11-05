"""Вход — из sk_common. Здесь только своё для SK Contest: режим судьи в ответе /me."""

from fastapi import Request
from sk_common.auth.router import create_auth_router, session_method
from sk_common.auth.schemas import Me
from sk_common.people.models import User
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.events.models import EventMember

JUDGE_QR = 'judge_qr'


class ContestMe(Me):
    """Профиль текущего пользователя с признаком режима судьи."""

    judge_mode: bool = False


async def _judge_mode(db: AsyncSession, request: Request, user: User) -> bool:
    """Интерфейс только для судейства: вход по QR-листу или у пользователя нет других ролей и заявок."""
    if user.is_superuser:
        return False
    if await session_method(db, request) == JUDGE_QR:
        return True
    if user.person and user.person.is_employee:
        return False
    roles = set(await db.scalars(select(EventMember.role).where(EventMember.user_id == user.id)))
    if roles != {'judge'}:
        return False
    return not await db.scalar(select(exists().where(Application.user_id == user.id)))


async def _me_extra(db: AsyncSession, request: Request, user: User) -> dict:
    """Дополняет профиль пользователя признаком судейского режима."""
    return {'judge_mode': await _judge_mode(db, request, user)}


router = create_auth_router(me_model=ContestMe, me_extra=_me_extra)
