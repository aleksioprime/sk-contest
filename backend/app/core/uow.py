from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import session_maker


class UnitOfWork:
    """Одна транзакция на операцию. Репозитории модулей получают сессию отсюда."""

    def __init__(self, factory: async_sessionmaker[AsyncSession] = session_maker):
        self._factory = factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self.session = self._factory()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


async def get_uow() -> UnitOfWork:
    return UnitOfWork()
