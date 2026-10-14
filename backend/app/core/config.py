from functools import cached_property

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    host: str = 'localhost'
    port: int = 5432
    user: str = 'sk_events'
    password: str = 'sk_events'
    name: str = 'sk_events'
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 10
    null_pool: bool = False  # для тестов: без пула, каждое соединение новое

    @property
    def dsn(self) -> str:
        return f'postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}'


class RedisSettings(BaseModel):
    host: str = 'localhost'
    port: int = 6379
    db: int = 0

    @property
    def dsn(self) -> str:
        return f'redis://{self.host}:{self.port}/{self.db}'


class SmtpSettings(BaseModel):
    """Яндекс: smtp.yandex.ru:465, SSL, логин — адрес ящика, пароль приложения. Отправитель совпадает с логином."""

    host: str = 'localhost'
    port: int = 1025
    user: str = ''
    password: str = ''
    use_ssl: bool = False
    sender: str = 'SK Events <skolstream@yandex.ru>'


class SkolstreamSettings(BaseModel):
    base_url: str = ''
    client_id: str = ''
    client_secret: str = ''
    directory_token: str = ''
    timeout: float = 20.0

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.client_id)


class CaptchaSettings(BaseModel):
    """Yandex SmartCaptcha: ключ клиента для виджета, ключ сервера для проверки."""

    client_key: str = ''
    server_key: str = ''

    @property
    def enabled(self) -> bool:
        return bool(self.client_key and self.server_key)


class AuthSettings(BaseModel):
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    magic_link_ttl_minutes: int = 20
    magic_link_per_hour: int = 5
    magic_link_per_ip_hour: int = 30
    access_cookie: str = 'ske_access'
    refresh_cookie: str = 'ske_refresh'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        extra='ignore',
    )

    environment: str = Field(default='local', description='local, uat или prod')
    project_name: str = 'SK Events'
    version: str = '0.1.0'
    secret_key: str = 'change-me'

    app_url: str = 'http://localhost:8501'
    sites_base_domain: str = 'events.skolhub.ru'
    # Свои домены лендингов: CNAME на этот адрес, маршрут в Traefik ведёт на сервис sites
    sites_cname_target: str = 'sites.events.skolhub.ru'
    sites_upstream_url: str = 'http://sites:3000'
    traefik_dynamic_dir: str = ''  # пусто — файлы маршрутов не пишутся (локальная разработка)
    traefik_certresolver: str = 'letsencrypt'
    cors_origins: list[str] = ['http://localhost:8501', 'http://localhost:8502']
    storage_dir: str = './.data/files'
    # Адреса, которые получают права администратора платформы при входе (первичная настройка)
    bootstrap_admin_emails: list[str] = []
    # Начальный пароль этих администраторов (задаётся один раз, пока пароля нет)
    bootstrap_admin_password: str = ''

    db: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    smtp: SmtpSettings = SmtpSettings()
    skolstream: SkolstreamSettings = SkolstreamSettings()
    auth: AuthSettings = AuthSettings()
    captcha: CaptchaSettings = CaptchaSettings()

    @cached_property
    def is_local(self) -> bool:
        return self.environment == 'local'

    @property
    def cookie_secure(self) -> bool:
        return not self.is_local

    @property
    def allowed_origins(self) -> set[str]:
        return {origin.rstrip('/') for origin in [*self.cors_origins, self.app_url]}


settings = Settings()
