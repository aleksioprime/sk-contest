# SK Contest

Платформа мероприятий Гимназии Сколково: конкурсы, конференции, олимпиады, фестивали, открытые события и отборы.

Организатор создаёт мероприятие, принимает заявки через открытую форму или вебхук из внешних сервисов, комплектует оценочные листы, раздаёт их судьям, ведёт участников по этапам и публикует итоги.

> Предыдущая версия (оценка работ поверх NocoBase) лежит в ветке
> [`archive/nocobase-v1`](https://github.com/aleksioprime/sk-contest/tree/archive/nocobase-v1), последний коммит отмечен тегом `v1-nocobase-final`.

## Запуск для разработки

Нужны Docker и Docker Compose.

```bash
docker compose -p sk-contest up -d --build
```

| Сервис | Адрес |
|---|---|
| Приложение (оргкомитет, кабинет, судья) | http://localhost:8501 |
| API и документация | http://localhost:8500/api/docs |
| Почта (Mailpit) | http://localhost:8504 |
| PostgreSQL / Redis | localhost:8510 / localhost:8511 |

Проверки, как в CI:

```bash
docker compose -p sk-contest exec backend sh -c "ruff check . && ruff format --check . && pytest -q"
```

```bash
npm ci && npm run lint && npm test && npm run build
```

## Структура

| Каталог | Что внутри |
|---|---|
| `backend/` | FastAPI, SQLAlchemy, Alembic, фоновые задачи arq |
| `frontend/` | Vue 3 SPA: открытая форма заявки, оргкомитет, кабинет участника, судья |
| `infra/` | конфигурация nginx, compose для Coolify |

## Документация

| Документ | О чём |
|---|---|
| [docs/plan.md](docs/plan.md) | План работ по этапам, задачи и вехи |
| [docs/development.md](docs/development.md) | Правила разработки, окружение, проверки |
| [docs/architecture.md](docs/architecture.md) | Стек, сервисы, модули backend, структура репозитория |
| [docs/registration.md](docs/registration.md) | Приём заявок: открытая форма, вебхук, подтверждение, связь с людьми из базы |
| [docs/integrations/skolstream.md](docs/integrations/skolstream.md) | Вход через SkolStream, синхронизация справочников, портфолио |
| [docs/legacy/nocobase.md](docs/legacy/nocobase.md) | Модель и формулы старой системы, найденные ошибки, перенос данных |
| [docs/decisions.md](docs/decisions.md) | Принятые и открытые решения |

## Прод

Приложение и API — **https://contest.skolhub.ru**, открытые формы заявок — `https://contest.skolhub.ru/apply/<адрес>`.
Coolify `devops.skolhub.ru`, сервер `skl-web-app`, ресурс разворачивается по
[`infra/coolify/docker-compose.prod.yaml`](infra/coolify/docker-compose.prod.yaml) из готовых образов
`ghcr.io/aleksioprime/sk-contest-*`, которые собирает [images.yml](.github/workflows/images.yml).
Старое приложение на NocoBase выведено из эксплуатации; его код — в ветке `archive/nocobase-v1`.

---

© 2026 Алексей Семочкин · Сервисы автоматизации Гимназии Сколково
