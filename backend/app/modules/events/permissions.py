"""Права в мероприятии. Администратор платформы может всё; остальные — по ролям в event_members."""

from fastapi import HTTPException, status
from sk_common.people.models import User

from app.modules.events.models import Event


def roles_of(user: User, event: Event) -> list[str]:
    """Роли пользователя в мероприятии."""
    return sorted({member.role for member in event.members if member.user_id == user.id})


def can_create_event(user: User) -> bool:
    """Может ли пользователь создавать мероприятия: суперпользователь или сотрудник."""
    return user.is_superuser or bool(user.person and user.person.is_employee)


def can_manage(user: User, event: Event) -> bool:
    """Может ли пользователь управлять мероприятием: суперпользователь или организатор."""
    return user.is_superuser or 'organizer' in roles_of(user, event)


def can_view(user: User, event: Event) -> bool:
    """Может ли пользователь видеть мероприятие: суперпользователь или член команды."""
    return user.is_superuser or bool(roles_of(user, event))


def ensure_manage(user: User, event: Event) -> None:
    """Бросает 403, если пользователь не может управлять мероприятием."""
    if not can_manage(user, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Изменять мероприятие могут только его организаторы')


def ensure_view(user: User, event: Event) -> None:
    """Бросает 404, если пользователь не может видеть мероприятие."""
    if not can_view(user, event):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Мероприятие не найдено')
