from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = Field(alias='PROJECT_NAME', default='SK Contest API')
    project_description: str = Field(
        alias='PROJECT_DESCRIPTION',
        default='Backend for Frontend — анонимная оценка работ SK Contest',
    )

    default_host: str = Field(alias='HOST', default='0.0.0.0')
    default_port: int = Field(alias='PORT', default=8000)
    api_prefix: str = '/api/v1'

    nocobase_url: str = Field(alias='NOCOBASE_URL', default='https://flow.skeducator.ru')
    nocobase_api_key: str = Field(alias='NOCOBASE_API_KEY', default='')
    nocobase_timeout: float = Field(alias='NOCOBASE_TIMEOUT', default=30.0)

    cors_allow_origins_str: str = Field(
        alias='CORS_ALLOW_ORIGINS',
        default='http://localhost:3000,http://127.0.0.1:3000',
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins_str.split(',') if origin.strip()]

    @property
    def nocobase_api_url(self) -> str:
        return f'{self.nocobase_url}/api'


settings = Settings()
