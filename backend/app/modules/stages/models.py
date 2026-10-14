from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin
from app.modules.applications.models import Application

ADMITTED, SCHEDULED, EVALUATED, PASSED, NOT_PASSED, WITHDRAWN = (
    'admitted',
    'scheduled',
    'evaluated',
    'passed',
    'not_passed',
    'withdrawn',
)
STATUSES = (ADMITTED, SCHEDULED, EVALUATED, PASSED, NOT_PASSED, WITHDRAWN)
IN_STAGE = (ADMITTED, SCHEDULED, EVALUATED)  # участник ещё проходит этап


class DefenseSlot(IdMixin, TimestampMixin, Base):
    """Время и место очной защиты: аудитория, начало и конец."""

    __tablename__ = 'stage_slots'

    stage_id: Mapped[int] = mapped_column(ForeignKey('event_stages.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200), default='')
    room: Mapped[str] = mapped_column(String(100), default='')
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StageParticipation(IdMixin, TimestampMixin, Base):
    """Участие заявки в этапе мероприятия."""

    __tablename__ = 'stage_participations'
    __table_args__ = (UniqueConstraint('stage_id', 'application_id'),)

    stage_id: Mapped[int] = mapped_column(ForeignKey('event_stages.id', ondelete='CASCADE'), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ADMITTED)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey('stage_slots.id', ondelete='SET NULL'))
    slot_order: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rank: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default='')

    application: Mapped[Application] = relationship(lazy='joined')
    slot: Mapped[DefenseSlot | None] = relationship(lazy='joined')
