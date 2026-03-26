# Жюри SK — Оценка конкурсных работ

Веб-приложение для оценки конкурсных работ жюри. Бэкенд — [NocoBase](https://www.nocobase.com/), фронтенд — Vue 3.

<div align="center">

**[Демо](https://contest.skeducator.ru)** · **[NocoBase API](https://flow.skeducator.ru)**

</div>

---

## Возможности

- **Авторизация** через NocoBase (логин / email + пароль)
- **Ролевая модель**: Judge (жюри), Viewer (наблюдатель), Admin
- **Переключение режимов** Judge ↔ Viewer для пользователей с двумя ролями
- **Оценочные листы** с фильтрацией по статусу (`active` / `inactive` / `archived`) и роли
- **Список работ** с участниками, руководителями, статусом оценки
- **Оценка работ** (Judge): выбор уровня по каждому критерию с оптимистичным сохранением
- **Просмотр оценок** (Viewer): сводка по всем судьям, раскрывающиеся оценки по критериям
- **Категории критериев**: группировка, сворачивание, баллы по категориям
- **Комментарии**: к отдельным критериям и общий комментарий к работе
- **Сортировка работ**: по общему баллу, по категории, по месту
- **Автообновление** данных каждые 30 секунд (режим Viewer)
- **Sticky-панель итогов** с раскладкой по категориям и динамическим скруглением углов
- **Адаптивная вёрстка**: мобильные устройства, планшеты, десктоп
- **Тёмная тема** (через `prefers-color-scheme`)

---

## Технологии

| Слой | Технология | Версия |
|------|-----------|--------|
| Framework | Vue 3 (Composition API, `<script setup>`) | 3.5 |
| Сборщик | Vite | 8.0 |
| Стили | Tailwind CSS (`@tailwindcss/vite`) | 4.2 |
| Маршрутизация | vue-router | 4.6 |
| Состояние | Pinia | 3.0 |
| HTTP | Axios | 1.13 |
| Бэкенд | NocoBase REST API | 2.0 |
| Сервер | nginx (production) | alpine |
| Контейнеризация | Docker (multi-stage) | — |

---

## Архитектура

```
Браузер  ──►  nginx / Vite dev-сервер  ──►  NocoBase API
                    │                          (flow.skeducator.ru)
                    │
               Vue 3 SPA
         ┌──────────┴──────────┐
         │   Pinia (auth)      │
         │   vue-router        │
         │   Axios (api)       │
         └─────────────────────┘
```

### Модель данных NocoBase

```
contest_evaluation_sheets   ← оценочные листы (связь: contest, stage, judges, scorecard)
  └── contest_evaluation_sheet_works  ← работы в листе (связь: stage_participation)
        └── contest_evaluations       ← оценки судей (judge_id = person.id)
              └── contest_evaluation_items  ← оценки по критериям (criterion_id, level_id, score)

contest_scorecard_criteria      ← критерии оценивания (связь: category, scale)
contest_criterion_categories    ← категории критериев
contest_criterion_scale_levels  ← уровни шкалы (point, title)
persons                         ← персоны (user_id → связь с пользователем NocoBase)
```

> **Важно**: `judge_id` в оценках ссылается на `person.id`, а не `user.id`. Поэтому при авторизации приложение дополнительно загружает запись `persons` по `user_id`.

---

## Структура проекта

```
sk-contest/
├── docker-compose.yaml         # Development compose (hot-reload)
├── docker-compose.prod.yaml    # Production compose (GHCR image)
├── .env.example                # Шаблон переменных окружения
├── README.md
└── frontend/
    ├── Dockerfile              # Multi-stage: dev (node) → prod (nginx)
    ├── nginx/
    │   └── nginx.conf          # SPA-роутинг + проксирование /api/
    └── app/
        ├── index.html          # Точка входа HTML
        ├── package.json
        ├── vite.config.js      # Vite + Tailwind + dev-proxy
        └── src/
            ├── main.js         # Инициализация приложения
            ├── App.vue         # Корневой layout (header, main, footer)
            ├── style.css       # Tailwind + кастомная палитра цветов
            ├── api/
            │   └── index.js    # Axios-инстанс с Bearer-токеном и 401-редиректом
            ├── utils/
            │   └── logger.js   # Условный логгер (VITE_LOGGING)
            ├── router/
            │   └── index.js    # Маршруты + навигационные гарды
            ├── stores/
            │   └── auth.js     # Pinia: авторизация, роли, person-маппинг
            ├── components/
            │   └── AppHeader.vue   # Шапка с меню, ролью, переключателем режима
            └── views/
                ├── LoginView.vue           # Страница входа
                ├── SheetsView.vue          # Список оценочных листов
                ├── WorksView.vue           # Список работ в листе
                ├── EvaluationView.vue      # Оценка работы (Judge)
                └── ViewerEvaluationView.vue # Просмотр оценок (Viewer)
```

---

## Ролевая модель

| Роль | ID в NocoBase | Доступ |
|------|--------------|--------|
| **Judge** | `r_33jle168sny` | Оценка работ в активных листах, комментарии |
| **Viewer** | `r_wrjkkito308` | Просмотр всех оценок, сортировка, статистика |
| **Admin** | `admin` | Права Viewer + видит все листы (вкл. архивные) |

Пользователь с обеими ролями (Judge + Viewer/Admin) может переключаться между режимами через меню в шапке. Выбранный режим сохраняется в `localStorage`.

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
