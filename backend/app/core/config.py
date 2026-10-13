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
    cors_origins: list[str] = ['http://localhost:8501', 'http://localhost:8502']
    storage_dir: str = './.data/files'

    db: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    smtp: SmtpSettings = SmtpSettings()
    skolstream: SkolstreamSettings = SkolstreamSettings()

    @cached_property
    def is_local(self) -> bool:
        return self.environment == 'local'


settings = Settings()
