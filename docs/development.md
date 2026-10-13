# Разработка

Перед работой прочитайте [plan.md](plan.md) и [architecture.md](architecture.md).

## Язык

- Интерфейс, документация, комментарии в коде и сообщения коммитов — на русском.
- Идентификаторы в коде, имена таблиц и эндпоинтов — на английском.

## Backend

- Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2, arq.
- Модуль = `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `permissions.py` в `backend/app/modules/<name>/`.
- Роутеры тонкие, бизнес-логика в сервисах, одна транзакция на запрос через unit of work.
- Каждый эндпоинт проверяет права на сервере (роль пользователя в конкретном мероприятии).
- Изменение схемы — только миграцией Alembic.
- Подсчёт баллов и рангов только через `evaluation/service` в той же транзакции, что и изменение оценки.
- Изменения оценок, статусов заявок и итогов пишутся в `audit_log`.

## Frontend

- Vue 3 `<script setup>`, Pinia, Vue Router, Tailwind 4.
- API-клиент разбит по модулям в `frontend/src/api/`.
- Блоки лендингов живут только в `packages/blocks` и используются и редактором, и `sites`.

## Окружение

- Стек разработки: `docker compose -p sk-events up -d --build`, порты 8500–8511 (см. README).
- npm workspaces: `packages/*`, `frontend`, `sites`. Новые пакеты ставить с `--before=<дата двухнедельной давности>`.
- Первичные ключи генерирует PostgreSQL (`next_id()`), модели наследуют `IdMixin` из `app/core/db.py`.
- Python-окружение для запуска вне Docker: `backend/.venv` (uv, Python 3.12).
- Загруженные файлы хранятся на диске в volume `files_data` (`STORAGE_DIR`), доступ только через модуль `app/core/storage.py`.

## Проверки перед коммитом

- backend: `ruff check .`, `ruff format --check .`, `pytest` (тесты с БД — внутри контейнера `backend`)
- frontend, sites, blocks: `npm run lint`, `npm test`, `npm run build` из корня

## Старая система

- Код NocoBase-версии: ветка `archive/nocobase-v1`. Экраны судьи, наблюдателя и анонимной оценки переносить оттуда.
- Формулы и ошибки старого подсчёта: [legacy/nocobase.md](legacy/nocobase.md).
- `docker-compose.prod.yaml` в корне обслуживает старый прод `contest.skolhub.ru` через Coolify. Не удалять и не менять до переключения.
