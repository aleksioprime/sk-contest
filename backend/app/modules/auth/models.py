from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin


class MagicLinkToken(IdMixin, Base):
    """Одноразовая ссылка входа по email. Хранится только хеш токена."""

    __tablename__ = 'magic_link_tokens'

    email: Mapped[str] = mapped_column(String(255), index=True)
    # judge_qr — вход судьи по QR с распечатанного листа: привязан к учётной записи, а не к email
    purpose: Mapped[str] = mapped_column(String(20), default='email', server_default='email')
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    next_path: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(IdMixin, Base):
    """Сессия входа. Refresh-токен в httpOnly cookie, в БД — его хеш. Ротируется при каждом обновлении."""

    __tablename__ = 'auth_sessions'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    method: Mapped[str] = mapped_column(String(20))  # magic_link | skolstream | judge_qr
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
