FROM python:3.12-slim-bookworm AS base

WORKDIR /usr/src/app
ENV PYTHONPATH=/usr/src/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Moscow

RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["sh", "./entrypoint.sh"]

FROM base AS prod
COPY . .
RUN chmod +x entrypoint.sh && useradd --system --uid 1001 app && chown -R app /usr/src/app
USER app
ENTRYPOINT ["sh", "./entrypoint.sh"]
