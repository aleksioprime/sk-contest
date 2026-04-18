# Жюри SK — Оценка конкурсных работ

Веб-приложение для оценки конкурсных работ жюри на основе [NocoBase](https://flow.skeducator.ru)

Документация по структуре данных: [docs/database.md](docs/database.md)

---

## Ролевая модель

| Роль | ID в NocoBase | Доступ |
|------|--------------|--------|
| **Judge** | `r_33jle168sny` | Оценка работ в активных листах, комментарии |
| **Viewer** | `r_wrjkkito308` | Просмотр всех оценок, сортировка, статистика |
| **Admin** | `admin` | Права Viewer + видит все листы (вкл. архивные) |

Пользователь с несколькими ролями (Judge + Viewer/Admin) может переходить между разделами через меню в шапке: «Оценка работ» (Judge) и «Просмотр результатов» (Viewer). Если у пользователя только роль Judge — по умолчанию открывается оценка. Если нет роли Judge, а есть Viewer/Admin — открывается просмотр результатов.

---

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|-----------|---------|----------------------|
| `VITE_API_URL` | URL бэкенда NocoBase (используется dev-прокси Vite) | `https://flow.skeducator.ru` |
| `VITE_LOGGING` | Включить логирование в консоль (`1` / `0`) | `0` |
| `FRONTEND_IMAGE_TAG` | Тег Docker-образа для production | `latest` |

---

## Запуск

### Предварительные требования

- Docker и Docker Compose

### Разработка (dev)

```bash
# 1. Создать файл переменных окружения
cp .env.example .env

# 2. Запустить контейнер с hot-reload
docker compose -p sk-contest up -d --build

# 3. Открыть приложение
open http://localhost:3000
```

В режиме разработки:
- Исходники монтируются через volume (`frontend/app/src`)
- Изменения применяются мгновенно через Vite HMR
- API проксируется через Vite dev-сервер на `VITE_API_URL`
- Порт: `3000` → `5173` (внутри контейнера)

### Production

```bash
# Сборка и публикация образа
docker build --target prod \
  --build-arg VITE_API_URL=https://flow.skeducator.ru \
  --build-arg VITE_LOGGING=0 \
  -t ghcr.io/aleksioprime/sk-contest-frontend:latest \
  ./frontend

docker push ghcr.io/aleksioprime/sk-contest-frontend:latest

# Запуск на сервере
docker compose -f docker-compose.prod.yaml up -d
```

В production:
- Статика раздаётся через nginx
- API проксируется на `http://nocobase-app:13000/api/`
- Контейнер подключается к внешней сети `apps_net`
- SPA fallback: все маршруты возвращают `index.html`

---

## Цветовая схема

| Цвет | CSS-переменная | Hex | Назначение |
|------|---------------|-----|-----------|
| Primary | `--color-primary` | `#7c3aed` | Бренд, кнопки, ссылки |
| Primary hover | `--color-primary-hover` | `#6d28d9` | Hover-состояние |
| Score | `--color-score` | `#d97706` | Баллы, оценки, итоговая панель |
| Success | `--color-success` | `#16a34a` | Успешные действия |
| Danger | `--color-danger` | `#dc2626` | Ошибки, удаление |

---

## Лицензия

© 2026 Алексей Семочкин · Сервисы автоматизации Гимназии Сколково
