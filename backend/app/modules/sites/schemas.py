from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DraftIn(BaseModel):
    content: dict[str, Any]


class PublishIn(BaseModel):
    note: str = Field(default='', max_length=200)


class DomainIn(BaseModel):
    domain: str = Field(min_length=3, max_length=300)


class DomainOut(BaseModel):
    id: int
    domain: str
    status: str
    error: str
    checked_at: datetime | None
    verified_at: datetime | None
    url: str


class VersionOut(BaseModel):
    id: int
    number: int
    note: str
    created_at: datetime
    created_by: str | None
    published: bool


class SiteOut(BaseModel):
    exists: bool
    draft: dict[str, Any] | None
    updated_at: datetime | None
    published_at: datetime | None
    published_version: int | None
    has_unpublished_changes: bool
    urls: list[str] = Field(description='Адреса лендинга: поддомен, путь на общем домене, свои домены')
    cname_target: str
    domains: list[DomainOut]
