from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin


class Site(IdMixin, TimestampMixin, Base):
    """Лендинг мероприятия: черновик правится в конструкторе, опубликованная версия видна посетителям."""

    __tablename__ = 'sites'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), unique=True)
    draft: Mapped[dict] = mapped_column(JSONB)
    published_version_id: Mapped[int | None] = mapped_column(
        ForeignKey('site_versions.id', ondelete='SET NULL', use_alter=True)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    domains: Mapped[list['SiteDomain']] = relationship(
        cascade='all, delete-orphan', lazy='selectin', order_by='SiteDomain.created_at'
    )


class SiteVersion(IdMixin, Base):
    """Снимок сайта при публикации. Из любой версии можно вернуть черновик."""

    __tablename__ = 'site_versions'
    __table_args__ = (UniqueConstraint('site_id', 'number'),)

    site_id: Mapped[int] = mapped_column(ForeignKey('sites.id', ondelete='CASCADE'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(String(200), default='', server_default='')
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteDomain(IdMixin, TimestampMixin, Base):
    """Свой домен лендинга. Активен, когда CNAME указывает на наш сервер и выпущен сертификат."""

    __tablename__ = 'site_domains'

    site_id: Mapped[int] = mapped_column(ForeignKey('sites.id', ondelete='CASCADE'), index=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')  # pending | active | error
    error: Mapped[str] = mapped_column(Text, default='', server_default='')
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
