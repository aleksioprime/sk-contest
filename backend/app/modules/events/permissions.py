"""Права в мероприятии. Администратор платформы может всё; остальные — по ролям в event_members."""

from fastapi import HTTPException, status

from app.modules.events.models import Event
from app.modules.people.models import User


def roles_of(user: User, event: Event) -> list[str]:
    return sorted({member.role for member in event.members if member.user_id == user.id})


def can_create_event(user: User) -> bool:
    return user.is_superuser or bool(user.person and user.person.is_employee)


def can_manage(user: User, event: Event) -> bool:
    return user.is_superuser or 'organizer' in roles_of(user, event)


def can_view(user: User, event: Event) -> bool:
    return user.is_superuser or bool(roles_of(user, event))


def ensure_manage(user: User, event: Event) -> None:
    if not can_manage(user, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Изменять мероприятие могут только его организаторы')


def ensure_view(user: User, event: Event) -> None:
    if not can_view(user, event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
