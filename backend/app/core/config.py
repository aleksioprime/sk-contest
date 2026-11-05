"""Настройки приложения: значения по умолчанию для общих настроек sk_common."""

import sk_common
from sk_common.config import AuthSettings, DatabaseSettings, ServiceSettings, SmtpSettings


class ContestDatabaseSettings(DatabaseSettings):
    """Параметры подключения к БД с прежними значениями по умолчанию."""

    user: str = 'sk_events'
    password: str = 'sk_events'
    name: str = 'sk_events'


class ContestSmtpSettings(SmtpSettings):
    """Параметры SMTP с адресом отправителя конкурса."""

    sender: str = 'SK Contest <skolstream@yandex.ru>'


class ContestAuthSettings(AuthSettings):
    # Имена cookie прежние, чтобы при обновлении никого не разлогинило
    """Настройки авторизации; имена cookie сохранены, чтобы после обновления сессии не сбрасывались."""

    access_cookie: str = 'ske_access'
    refresh_cookie: str = 'ske_refresh'


class Settings(ServiceSettings):
    """Общие поля (БД, Redis, почта, SkolStream, вход) — в sk_common.config.ServiceSettings."""

    project_name: str = 'SK Contest'
    brand_color: str = '#6d28d9'

    cors_origins: list[str] = ['http://localhost:8501']
    storage_dir: str = './.data/files'
    # Перенос истории из NocoBase (python -m app.cli nocobase-fetch)
    nocobase_url: str = ''
    nocobase_api_key: str = ''

    db: ContestDatabaseSettings = ContestDatabaseSettings()
    smtp: ContestSmtpSettings = ContestSmtpSettings()
    auth: ContestAuthSettings = ContestAuthSettings()


settings = Settings()
sk_common.configure(settings)
