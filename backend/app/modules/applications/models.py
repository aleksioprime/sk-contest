from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin
from app.modules.events.models import Direction, Event, ParticipationForm
from app.modules.files.models import StoredFile
from app.modules.people.models import User

DRAFT, SUBMITTED, NEEDS_CHANGES, ACCEPTED, REJECTED, WITHDRAWN = (
    'draft',
    'submitted',
    'needs_changes',
    'accepted',
    'rejected',
    'withdrawn',
)
EDITABLE = {DRAFT, NEEDS_CHANGES}
DECISIONS = {ACCEPTED, NEEDS_CHANGES, REJECTED, SUBMITTED}  # SUBMITTED — вернуть на рассмотрение
ACTIVE = {SUBMITTED, NEEDS_CHANGES, ACCEPTED}  # учитываются в лимитах


class Application(IdMixin, TimestampMixin, Base):
    __tablename__ = 'applications'
    __table_args__ = (UniqueConstraint('event_id', 'number'),)

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(300), default='', server_default='')
    direction_id: Mapped[int | None] = mapped_column(ForeignKey('event_directions.id', ondelete='SET NULL'))
    participation_form_id: Mapped[int | None] = mapped_column(
        ForeignKey('event_participation_forms.id', ondelete='SET NULL')
    )
    status: Mapped[str] = mapped_column(String(20), default=DRAFT, server_default=DRAFT, index=True)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    moderator_comment: Mapped[str] = mapped_column(Text, default='', server_default='')
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))

    event: Mapped[Event] = relationship(lazy='joined')
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy='joined')
    direction: Mapped[Direction | None] = relationship(lazy='joined')
    participation_form: Mapped[ParticipationForm | None] = relationship(lazy='joined')
    members: Mapped[list['ApplicationMember']] = relationship(
        back_populates='application', order_by='ApplicationMember.order', cascade='all, delete-orphan', lazy='selectin'
    )
    consents: Mapped[list['ApplicationConsent']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    files: Mapped[list['ApplicationFile']] = relationship(cascade='all, delete-orphan', lazy='selectin')


class ApplicationMember(IdMixin, Base):
    """Участник или руководитель в заявке. Может не иметь учётной записи."""

    __tablename__ = 'application_members'

    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(20))  # participant | supervisor
    person_id: Mapped[int | None] = mapped_column(ForeignKey('persons.id', ondelete='SET NULL'), index=True)
    full_name: Mapped[str] = mapped_column(String(300))
    email: Mapped[str] = mapped_column(String(255), default='', server_default='')
    grade: Mapped[str] = mapped_column(String(20), default='', server_default='')
    organization: Mapped[str] = mapped_column(String(300), default='', server_default='')
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    application: Mapped[Application] = relationship(back_populates='members')


class ApplicationConsent(IdMixin, Base):
    """Факт согласия: какой текст (ключ и версия), кто и когда принял."""

    __tablename__ = 'application_consents'

    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    key: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    ip: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationFile(Base):
    __tablename__ = 'application_files'

    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('files.id', ondelete='CASCADE'), primary_key=True)
    field_key: Mapped[str] = mapped_column(String(40))

    file: Mapped[StoredFile] = relationship(lazy='joined')
