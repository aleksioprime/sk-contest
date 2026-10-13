#!/bin/sh
# Роли контейнера: api (по умолчанию), worker, migrate.
set -e

DB_HOST="${DB__HOST:-postgres}"
DB_PORT="${DB__PORT:-5432}"

echo "Ожидание базы данных ${DB_HOST}:${DB_PORT}..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 0.2
done

case "${1:-api}" in
    api)
        alembic upgrade head
        if [ "${RELOAD:-0}" = "1" ]; then
            exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
        fi
        exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
            -w "${WORKERS:-2}" -b 0.0.0.0:8000 --access-logfile -
        ;;
    worker)
        exec arq app.workers.main.WorkerSettings
        ;;
    migrate)
        exec alembic upgrade head
        ;;
    *)
        exec "$@"
        ;;
esac
