from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin
from app.modules.people.models import AcademicYear, User


class Event(IdMixin, TimestampMixin, Base):
    __tablename__ = 'events'

    slug: Mapped[str] = mapped_column(String(63), unique=True)
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    short_description: Mapped[str] = mapped_column(String(300), default='', server_default='')
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    status: Mapped[str] = mapped_column(String(20), default='draft', server_default='draft', index=True)
    level: Mapped[str] = mapped_column(String(20), default='school', server_default='school')
    format: Mapped[str] = mapped_column(String(20), default='onsite', server_default='onsite')
    place: Mapped[str] = mapped_column(String(300), default='', server_default='')
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey('academic_years.id', ondelete='SET NULL'))
    copied_from_id: Mapped[int | None] = mapped_column(ForeignKey('events.id', ondelete='SET NULL'))
    cover_file_id: Mapped[int | None] = mapped_column(ForeignKey('files.id', ondelete='SET NULL'))
    # Анкета заявки: поля, команда, ограничения и согласия (схема в app/modules/applications/form.py)
    application_form: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    results_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Награды и оформление дипломов: {"winners": 1, "prize_places": 3, "signatory": "...", "signatory_title": "..."}
    awards: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))

    academic_year: Mapped[AcademicYear | None] = relationship(lazy='joined')
    directions: Mapped[list['Direction']] = relationship(
        back_populates='event', order_by='Direction.order', cascade='all, delete-orphan', lazy='selectin'
    )
    stages: Mapped[list['Stage']] = relationship(
        back_populates='event', order_by='Stage.order', cascade='all, delete-orphan', lazy='selectin'
    )
    participation_forms: Mapped[list['ParticipationForm']] = relationship(
        back_populates='event', order_by='ParticipationForm.order', cascade='all, delete-orphan', lazy='selectin'
    )
    members: Mapped[list['EventMember']] = relationship(
        back_populates='event', cascade='all, delete-orphan', lazy='selectin'
    )


class Direction(IdMixin, TimestampMixin, Base):
    """Направление или номинация мероприятия."""

    __tablename__ = 'event_directions'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    event: Mapped[Event] = relationship(back_populates='directions')


class Stage(IdMixin, TimestampMixin, Base):
    """Этап мероприятия: заочный отбор, очная защита, финал и т. п."""

    __tablename__ = 'event_stages'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default='onsite', server_default='onsite')  # remote | onsite
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    # Правило перехода на следующий этап: {"type": "top_n|threshold|manual", "n", "per_direction", "threshold"}
    advance_rule: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    # Места на этапе: по направлениям или общий рейтинг (финал, где все защищаются по одним критериям)
    rank_scope: Mapped[str] = mapped_column(String(20), default='direction', server_default='direction')
    # Несколько листов этапа (например, по дням): как объединять баллы работы, если она есть в нескольких листах
    score_combine: Mapped[str] = mapped_column(String(20), default='avg', server_default='avg')  # avg | sum | max

    event: Mapped[Event] = relationship(back_populates='stages')


class ParticipationForm(IdMixin, TimestampMixin, Base):
    """Форма участия: доклад, стендовая защита, слушатель и т. п."""

    __tablename__ = 'event_participation_forms'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    event: Mapped[Event] = relationship(back_populates='participation_forms')


class EventMember(IdMixin, TimestampMixin, Base):
    """Роль пользователя в мероприятии."""

    __tablename__ = 'event_members'
    __table_args__ = (UniqueConstraint('event_id', 'user_id', 'role'),)

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(20))  # organizer | moderator | judge | observer

    event: Mapped[Event] = relationship(back_populates='members')
    user: Mapped[User] = relationship(lazy='joined')
