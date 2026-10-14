"""Кто может скачать файл: владелец, администратор, организаторы и модераторы мероприятия, судьи листа с работой."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models import StoredFile
from app.modules.people.models import User

STAFF_ROLES = ('organizer', 'moderator')


async def can_read(session: AsyncSession, user: User, stored: StoredFile) -> bool:
    if stored.is_public or user.is_superuser or stored.owner_id == user.id:
        return True
    from app.modules.applications.models import Application, ApplicationFile
    from app.modules.events.models import EventMember

    query = (
        select(ApplicationFile.file_id)
        .join(Application, Application.id == ApplicationFile.application_id)
        .join(EventMember, EventMember.event_id == Application.event_id)
        .where(
            ApplicationFile.file_id == stored.id,
            EventMember.user_id == user.id,
            EventMember.role.in_(STAFF_ROLES),
        )
        .limit(1)
    )
    if await session.scalar(query) is not None:
        return True
    from app.modules.evaluation.models import SheetJudge, SheetWork

    judge_query = (
        select(ApplicationFile.file_id)
        .join(SheetWork, SheetWork.application_id == ApplicationFile.application_id)
        .join(SheetJudge, SheetJudge.sheet_id == SheetWork.sheet_id)
        .where(ApplicationFile.file_id == stored.id, SheetJudge.user_id == user.id)
        .limit(1)
    )
    return await session.scalar(judge_query) is not None
