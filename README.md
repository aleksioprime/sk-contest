# SK Contest — Оценка конкурсных работ

Фронтенд для оценки конкурсных работ с бэкендом NocoBase.

## Запуск

1. Скопируйте файл переменных окружения и при необходимости измените `API_URL`:

```bash
cp .env.example .env
```

2. Соберите и запустите контейнер:

```bash
docker compose -p sk-contest up -d --build
```

3. Откройте приложение: [http://localhost:3000](http://localhost:3000)
