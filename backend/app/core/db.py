from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, MetaData, func, text
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import settings

NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    """53-битный snowflake из функции next_id() (миграция 0001): безопасен для JavaScript, больше ID из NocoBase."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=text('next_id()'))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


if settings.db.null_pool:
    engine = create_async_engine(settings.db.dsn, echo=settings.db.echo, poolclass=NullPool)
else:
    engine = create_async_engine(
        settings.db.dsn,
        echo=settings.db.echo,
        pool_pre_ping=True,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
    )
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_maker() as session:
        yield session
