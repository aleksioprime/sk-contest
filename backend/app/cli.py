"""Служебные команды: python -m app.cli bootstrap."""

import asyncio
import json
import logging
import sys
from pathlib import Path

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


async def nocobase_fetch(target: str) -> None:
    from app.legacy.nocobase import fetch

    if not settings.nocobase_url or not settings.nocobase_api_key:
        sys.exit('Задайте NOCOBASE_URL и NOCOBASE_API_KEY')
    counts = await fetch(settings.nocobase_url, settings.nocobase_api_key, Path(target))
    print(json.dumps(counts, ensure_ascii=False, indent=1))


async def nocobase_load(source: str) -> None:
    from app.legacy.nocobase import load

    async with UnitOfWork() as uow:
        report = await load(uow.session, Path(source))
    print(json.dumps(report['counts'], ensure_ascii=False, indent=1))
    print(f'Пропущено: { {k: len(v) for k, v in report["skipped"].items()} }')
    print(f'Изменились баллы работ: {len(report["score_changes"])}. Подробно: {source}/report.json')


def main() -> None:
    command, *args = sys.argv[1:] or ['']
    if command == 'bootstrap':
        asyncio.run(bootstrap())
    elif command == 'nocobase-fetch' and args:
        asyncio.run(nocobase_fetch(args[0]))
    elif command == 'nocobase-load' and args:
        asyncio.run(nocobase_load(args[0]))
    else:
        print('Команды: bootstrap | nocobase-fetch <каталог> | nocobase-load <каталог>')
        sys.exit(1)


if __name__ == '__main__':
    main()
