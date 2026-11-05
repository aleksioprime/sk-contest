"""Служебные команды: python -m app.cli bootstrap."""

import asyncio
import json
import logging
import sys
from pathlib import Path

from sk_common.cli import bootstrap
from sk_common.uow import UnitOfWork

from app.core.config import settings

logger = logging.getLogger('sk_contest.cli')


async def nocobase_fetch(target: str) -> None:
    """Выгружает данные старой системы NocoBase в каталог target как JSON и печатает число записей по таблицам."""
    from app.legacy.nocobase import fetch

    if not settings.nocobase_url or not settings.nocobase_api_key:
        sys.exit('Задайте NOCOBASE_URL и NOCOBASE_API_KEY')
    counts = await fetch(settings.nocobase_url, settings.nocobase_api_key, Path(target))
    print(json.dumps(counts, ensure_ascii=False, indent=1))


async def nocobase_load(source: str) -> None:
    """Загружает выгрузку NocoBase из каталога source в БД и печатает сводку загрузки."""
    from app.legacy.nocobase import load

    async with UnitOfWork() as uow:
        report = await load(uow.session, Path(source))
    print(json.dumps(report['counts'], ensure_ascii=False, indent=1))
    print(f'Пропущено: { {k: len(v) for k, v in report["skipped"].items()} }')
    print(f'Изменились баллы работ: {len(report["score_changes"])}. Подробно: {source}/report.json')


def main() -> None:
    """Точка входа CLI: выбирает команду по первому аргументу командной строки."""
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
