# Разработка

Перед работой прочитайте [plan.md](plan.md) и [architecture.md](architecture.md).

## Язык

- Интерфейс, документация, комментарии в коде и сообщения коммитов — на русском.
- Идентификаторы в коде, имена таблиц и эндпоинтов — на английском.

## Backend

- Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2, arq.
- Модуль = `models.py`, `schemas.py`, `service.py`, `router.py` в `backend/app/modules/<name>/`, при необходимости отдельные файлы под части логики.
- Роутеры тонкие, бизнес-логика в сервисах, одна транзакция на запрос. Функции и модули — с краткими докстрингами на русском.
- Каждый эндпоинт проверяет права на сервере (роль пользователя в конкретном мероприятии).
- Изменение схемы — только миграцией Alembic.
- Подсчёт баллов и рангов только через `evaluation/service` в той же транзакции, что и изменение оценки.
- Изменения оценок, статусов заявок и итогов пишутся в `audit_log`.

## Frontend

- Vue 3 `<script setup>`, Pinia, Vue Router, Tailwind 4.
- API-клиент разбит по модулям в `frontend/src/api/`.

## Окружение

- Стек разработки: `docker compose -p sk-contest up -d --build`, порты 8500–8511 (см. README).
- npm workspaces: `frontend`. Новые пакеты ставить с `--before=<дата двухнедельной давности>`.
- Первичные ключи генерирует PostgreSQL (`next_id()`), модели наследуют `IdMixin` из `app/core/db.py`.
- Python-окружение для запуска вне Docker: `backend/.venv` (uv, Python 3.12).
- Загруженные файлы хранятся на диске в volume `files_data` (`STORAGE_DIR`), доступ только через модуль `app/core/storage.py`.

## Проверки перед коммитом

- backend: `ruff check .`, `ruff format --check .`, `pytest` (тесты с БД — внутри контейнера `backend`)
- frontend: `npm run lint`, `npm test`, `npm run build` из корня

## Старая система

- Код NocoBase-версии: ветка `archive/nocobase-v1`. Экраны судьи, наблюдателя и анонимной оценки переносить оттуда.
- Формулы и ошибки старого подсчёта: [legacy/nocobase.md](legacy/nocobase.md).
- Старое приложение на NocoBase выведено из эксплуатации, его `docker-compose.prod.yaml` удалён; `contest.skolhub.ru` теперь обслуживает это приложение.
