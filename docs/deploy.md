# Развёртывание в Coolify

Прод собирается на сервере Coolify из этого репозитория: ресурс «Docker Compose» с файлом
[`infra/coolify/docker-compose.prod.yaml`](../infra/coolify/docker-compose.prod.yaml).
API идёт через nginx фронтенда, поэтому приложению нужен один домен.

## 1. DNS (REG.RU)

A-записи на IP сервера Coolify:

| Запись | Для чего |
|---|---|
| `contest.skolhub.ru` | приложение и API |
| `sites.contest.skolhub.ru` | лендинги по пути `/slug` |
| `*.sites.contest.skolhub.ru` | лендинги на поддоменах (сертификат — [domains.md](domains.md)) |
| `sites.contest.skolhub.ru` | цель CNAME для своих доменов организаторов |

## 2. Переменные

Заполните раздел SK Contest в `.env.prod` (файл не попадает в git): email и пароль первого администратора,
токен API Coolify; почту и капчу — когда появятся. `SECRET_KEY` и пароль БД уже сгенерированы.

## 3. Ресурс в Coolify

Автоматически:

```bash
python3 infra/coolify/deploy.py --dry-run
python3 infra/coolify/deploy.py
```

Скрипт создаёт ресурс `sk-contest` в проекте Contest панели `devops.skolhub.ru` (сервер `skl-web-app`),
передаёт переменные из `.env.prod`, задаёт домены и запускает сборку. В `.env.prod` нужны
`COOLIFY_URL=https://devops.skolhub.ru` и `COOLIFY_API_TOKEN`.

Вручную: *New Resource → Public Repository → main → Docker Compose*,
путь `/infra/coolify/docker-compose.prod.yaml`; переменные из `.env.prod`; домены
`frontend` → `https://contest.skolhub.ru`, `sites` → `https://sites.contest.skolhub.ru`.

DNS: `contest.skolhub.ru` и `*.contest.skolhub.ru` (для `sites.contest.skolhub.ru`) — A‑записи на `5.252.65.50`.

## 4. Первый вход

`https://contest.skolhub.ru` → «По паролю» → email и пароль из `BOOTSTRAP_ADMIN_*`.
В разделе «Люди» администратор создаёт сотрудников (они могут создавать мероприятия) и задаёт им пароли.

## 5. Перенос истории из NocoBase

Разовая операция, приложение с NocoBase не связано. Выгрузка делается на любой машине с доступом к NocoBase
(ключ API только на время выгрузки), затем JSON-файлы копируются в том `nocobase_data` контейнера `backend`:

```bash
NOCOBASE_URL=https://flow.skolhub.ru NOCOBASE_API_KEY=… python -m app.cli nocobase-fetch ./nocobase
python -m app.cli nocobase-load /data/nocobase   # в контейнере backend на сервере
```

Первая команда только читает API NocoBase и сохраняет коллекции в JSON. Вторая переносит конкурсы в архив SK Contest с исходными ID, пересчитывает баллы и места
и пишет `report.json`: что пропущено и у каких работ изменился балл (в NocoBase часть баллов посчитана
по первым 20 оценкам). Повторный запуск не дублирует уже перенесённые конкурсы.

Судьи получают учётные записи по email из NocoBase; пароли им задаёт администратор или они входят по ссылке из письма.

## 6. Резервные копии

База работает внутри ресурса compose, поэтому встроенные бэкапы Coolify для неё не включаются.
До отдельной настройки (restic, план этапа 0) — задача *Scheduled Tasks* в ресурсе для контейнера `postgres`
раз в сутки: `pg_dump -U sk_events sk_events | gzip > /var/lib/postgresql/data/backup-$(date +%u).sql.gz`
(семь копий по дням недели). Файлы участников — том `files_data`.
