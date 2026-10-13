# SK Events

Платформа мероприятий Гимназии Сколково: конкурсы, конференции, олимпиады, фестивали, открытые события и отборы.

Организатор создаёт мероприятие, собирает его лендинг на поддомене, принимает заявки, комплектует оценочные листы, раздаёт их судьям, ведёт участников по этапам и публикует итоги.

> Проект в стадии подготовки к реализации. Предыдущая версия (оценка работ поверх NocoBase) лежит в ветке
> [`archive/nocobase-v1`](https://github.com/aleksioprime/sk-contest/tree/archive/nocobase-v1), последний коммит отмечен тегом `v1-nocobase-final`.

## Запуск для разработки

Нужны Docker и Docker Compose.

```bash
docker compose -p sk-events up -d --build
```

| Сервис | Адрес |
|---|---|
| Приложение (оргкомитет, кабинет, судья) | http://localhost:8501 |
| API и документация | http://localhost:8500/api/docs |
| Лендинги | http://localhost:8502, сайт по поддомену: заголовок `Host: <slug>.events.localhost` |
| Почта (Mailpit) | http://localhost:8504 |
| PostgreSQL / Redis | localhost:8510 / localhost:8511 |

Проверки, как в CI:

```bash
docker compose -p sk-events exec backend sh -c "ruff check . && ruff format --check . && pytest -q"
```

```bash
npm ci && npm run lint && npm test && npm run build
```

## Структура

| Каталог | Что внутри |
|---|---|
| `backend/` | FastAPI, SQLAlchemy, Alembic, фоновые задачи arq |
| `frontend/` | Vue 3 SPA: оргкомитет, кабинет участника, судья, редактор лендингов |
| `sites/` | Nuxt 4 SSR: публичные лендинги по заголовку Host |
| `packages/blocks/` | блоки лендингов: схемы и компоненты, общие для редактора и `sites` |
| `infra/` | конфигурация nginx, compose для Coolify |

## Документация

| Документ | О чём |
|---|---|
| [docs/plan.md](docs/plan.md) | План работ по этапам, задачи и вехи |
| [docs/development.md](docs/development.md) | Правила разработки, окружение, проверки |
| [docs/architecture.md](docs/architecture.md) | Стек, сервисы, модули backend, структура репозитория |
| [docs/event-types.md](docs/event-types.md) | Типы мероприятий и механики |
| [docs/landing-builder.md](docs/landing-builder.md) | Конструктор лендингов: блоки, редактирование, домены |
| [docs/integrations/skolstream.md](docs/integrations/skolstream.md) | Вход через SkolStream, синхронизация справочников, портфолио |
| [docs/legacy/nocobase.md](docs/legacy/nocobase.md) | Модель и формулы старой системы, найденные ошибки, перенос данных |
| [docs/decisions.md](docs/decisions.md) | Принятые и открытые решения |

## Текущий прод

`contest.skolhub.ru` пока обслуживает старое приложение. Coolify разворачивает его из `main` по файлу
[`docker-compose.prod.yaml`](docker-compose.prod.yaml), который подтягивает готовые образы из GHCR.
Файл нужно сохранить, пока новое приложение не заменит старое (этап 7 плана), либо заранее переключить
приложение `contest` в Coolify на ветку `archive/nocobase-v1`.

---

© 2026 Алексей Семочкин · Сервисы автоматизации Гимназии Сколково
