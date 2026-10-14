"""Кто может скачать файл: владелец, администратор и организаторы или модераторы мероприятия с этой заявкой."""

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
    return await session.scalar(query) is not None
