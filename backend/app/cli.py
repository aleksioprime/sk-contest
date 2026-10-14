"""Служебные команды: python -m app.cli bootstrap."""

import asyncio
import logging
import sys

from app.core.config import settings
from app.core.security import hash_password
from app.core.uow import UnitOfWork
from app.modules.people.service import find_or_create_user_by_email, set_employee

logger = logging.getLogger('sk_events.cli')


async def bootstrap() -> None:
    """Администраторы из BOOTSTRAP_ADMIN_EMAILS. Пароль BOOTSTRAP_ADMIN_PASSWORD задаётся, только если его ещё нет."""
    async with UnitOfWork() as uow:
        for email in settings.bootstrap_admin_emails:
            user = await find_or_create_user_by_email(uow.session, email)
            user.is_superuser = True
            await set_employee(uow.session, user, True)
            if settings.bootstrap_admin_password and not user.password_hash:
                user.password_hash = hash_password(settings.bootstrap_admin_password)
                print(f'Задан пароль администратора {email}')


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'bootstrap':
        asyncio.run(bootstrap())
    else:
        print('Команды: bootstrap')
        sys.exit(1)


if __name__ == '__main__':
    main()
