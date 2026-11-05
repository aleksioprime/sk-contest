"""Заявка проходит два шага: общая заявка на регистрацию, затем после подтверждения — полная анкета в кабинете."""

from datetime import datetime
from enum import StrEnum

from sk_common.db import Base, IdMixin, TimestampMixin
from sk_common.people.models import User
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.events.models import Direction, Event, ParticipationForm
from app.modules.files.models import StoredFile

REQUESTED, DRAFT, SUBMITTED, NEEDS_CHANGES, ACCEPTED, REJECTED, WITHDRAWN = (
    'requested',  # общая заявка ждёт подтверждения модератора
    'draft',  # подтверждена, участник заполняет анкету в кабинете
    'submitted',
    'needs_changes',
    'accepted',
    'rejected',
    'withdrawn',
)
EDITABLE = {DRAFT, NEEDS_CHANGES}
ACTIVE = {SUBMITTED, NEEDS_CHANGES, ACCEPTED}  # учитываются в лимитах


class Source(StrEnum):
    """Откуда пришла заявка."""

    FORM = 'form'  # открытая форма без входа
    WEBHOOK = 'webhook'  # внешнее приложение (например, Tilda)
    CABINET = 'cabinet'  # вошедший пользователь
    STAFF = 'staff'  # внёс оргкомитет
    IMPORT = 'import'  # перенесена из старой системы


class Application(IdMixin, TimestampMixin, Base):
    """Заявка на мероприятие: ответы формы, статус, источник, заявитель и члены команды."""

    __tablename__ = 'applications'
    __table_args__ = (
        UniqueConstraint('event_id', 'number'),
        UniqueConstraint('event_id', 'external_id', name='uq_applications_event_id_external_id'),
    )

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    # Учётная запись заявителя. Пусто только у открытой заявки, которую ещё не подтвердили и не связали с человеком
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    source: Mapped[str] = mapped_column(String(20), default=Source.CABINET, server_default=Source.CABINET)
    title: Mapped[str] = mapped_column(String(300), default='', server_default='')
    direction_id: Mapped[int | None] = mapped_column(ForeignKey('event_directions.id', ondelete='SET NULL'))
    participation_form_id: Mapped[int | None] = mapped_column(
        ForeignKey('event_participation_forms.id', ondelete='SET NULL')
    )
    status: Mapped[str] = mapped_column(String(20), default=DRAFT, server_default=DRAFT, index=True)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    # Контакты из общей заявки: по ним модератор находит человека, на email уходит приглашение
    contact_name: Mapped[str] = mapped_column(String(300), default='', server_default='')
    contact_email: Mapped[str] = mapped_column(String(255), default='', server_default='', index=True)
    contact_phone: Mapped[str] = mapped_column(String(40), default='', server_default='')
    contact_organization: Mapped[str] = mapped_column(String(300), default='', server_default='')
    contact_grade: Mapped[str] = mapped_column(String(20), default='', server_default='')
    # Вебхук: номер записи во внешней системе (защита от повторной доставки) и исходные данные для модератора
    external_id: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    moderator_comment: Mapped[str] = mapped_column(Text, default='', server_default='')
    # Когда модератор подтвердил общую заявку; пусто — заявка ещё на первом шаге
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Когда отправлено напоминание о незаконченном черновике
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))

    event: Mapped[Event] = relationship(lazy='joined')
    user: Mapped[User | None] = relationship(foreign_keys=[user_id], lazy='joined')
    direction: Mapped[Direction | None] = relationship(lazy='joined')
    participation_form: Mapped[ParticipationForm | None] = relationship(lazy='joined')
    members: Mapped[list['ApplicationMember']] = relationship(
        back_populates='application', order_by='ApplicationMember.order', cascade='all, delete-orphan', lazy='selectin'
    )
    consents: Mapped[list['ApplicationConsent']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    files: Mapped[list['ApplicationFile']] = relationship(cascade='all, delete-orphan', lazy='selectin')

    @property
    def applicant_email(self) -> str:
        """Адрес для писем: учётная запись, а до привязки — контакт из заявки."""
        return self.user.email if self.user else self.contact_email

    @property
    def applicant_name(self) -> str:
        """Имя заявителя для интерфейса."""
        person = self.user.person if self.user else None
        return (person.full_name if person else '') or self.contact_name or self.applicant_email


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
    """Связь заявки с загруженным файлом и полем формы, к которому он относится."""

    __tablename__ = 'application_files'

    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('files.id', ondelete='CASCADE'), primary_key=True)
    field_key: Mapped[str] = mapped_column(String(40))

    file: Mapped[StoredFile] = relationship(lazy='joined')
