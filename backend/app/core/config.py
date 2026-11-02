import sk_common
from sk_common.config import AuthSettings, DatabaseSettings, ServiceSettings, SmtpSettings


class ContestDatabaseSettings(DatabaseSettings):
    user: str = 'sk_events'
    password: str = 'sk_events'
    name: str = 'sk_events'


class ContestSmtpSettings(SmtpSettings):
    sender: str = 'SK Contest <skolstream@yandex.ru>'


class ContestAuthSettings(AuthSettings):
    # Имена cookie прежние, чтобы при обновлении никого не разлогинило
    access_cookie: str = 'ske_access'
    refresh_cookie: str = 'ske_refresh'


class Settings(ServiceSettings):
    """Общие поля (БД, Redis, почта, SkolStream, вход) — в sk_common.config.ServiceSettings."""

    project_name: str = 'SK Contest'
    brand_color: str = '#6d28d9'

    sites_base_domain: str = 'sites.contest.skolhub.ru'
    # Свои домены лендингов: CNAME на этот адрес, маршрут в Traefik ведёт на сервис sites
    sites_cname_target: str = 'sites.contest.skolhub.ru'
    sites_upstream_url: str = 'http://sites:3000'
    traefik_dynamic_dir: str = ''  # пусто — файлы маршрутов не пишутся (локальная разработка)
    traefik_certresolver: str = 'letsencrypt'
    cors_origins: list[str] = ['http://localhost:8501', 'http://localhost:8502']
    storage_dir: str = './.data/files'
    # Перенос истории из NocoBase (python -m app.cli nocobase-fetch)
    nocobase_url: str = ''
    nocobase_api_key: str = ''

    db: ContestDatabaseSettings = ContestDatabaseSettings()
    smtp: ContestSmtpSettings = ContestSmtpSettings()
    auth: ContestAuthSettings = ContestAuthSettings()


settings = Settings()
sk_common.configure(settings)
