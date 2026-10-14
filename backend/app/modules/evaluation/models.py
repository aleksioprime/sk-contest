from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin
from app.modules.applications.models import Application
from app.modules.people.models import User

Points = Numeric(8, 2)


class Scale(IdMixin, TimestampMixin, Base):
    """Шкала уровней, общая для нескольких критериев: «0 — нет, 1 — частично, 2 — полностью»."""

    __tablename__ = 'eval_scales'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))

    levels: Mapped[list['ScaleLevel']] = relationship(
        order_by='ScaleLevel.order', cascade='all, delete-orphan', lazy='selectin'
    )


class ScaleLevel(IdMixin, Base):
    __tablename__ = 'eval_scale_levels'

    scale_id: Mapped[int] = mapped_column(ForeignKey('eval_scales.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    points: Mapped[Decimal] = mapped_column(Points)
    order: Mapped[int] = mapped_column(Integer, default=0)


class Scorecard(IdMixin, TimestampMixin, Base):
    """Таблица оценок: категории и критерии."""

    __tablename__ = 'eval_scorecards'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))

    categories: Mapped[list['Category']] = relationship(
        order_by='Category.order', cascade='all, delete-orphan', lazy='selectin'
    )
    criteria: Mapped[list['Criterion']] = relationship(
        order_by='Criterion.order', cascade='all, delete-orphan', lazy='selectin'
    )


class Category(IdMixin, Base):
    __tablename__ = 'eval_categories'

    scorecard_id: Mapped[int] = mapped_column(ForeignKey('eval_scorecards.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    order: Mapped[int] = mapped_column(Integer, default=0)


class Criterion(IdMixin, Base):
    __tablename__ = 'eval_criteria'

    scorecard_id: Mapped[int] = mapped_column(ForeignKey('eval_scorecards.id', ondelete='CASCADE'), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('eval_categories.id', ondelete='SET NULL'))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default='')
    type: Mapped[str] = mapped_column(String(20), default='scale')  # scale | checklist
    scale_id: Mapped[int | None] = mapped_column(ForeignKey('eval_scales.id', ondelete='RESTRICT'))
    weight: Mapped[Decimal] = mapped_column(Points, default=Decimal(1))
    order: Mapped[int] = mapped_column(Integer, default=0)

    scale: Mapped[Scale | None] = relationship(lazy='joined')
    options: Mapped[list['CriterionOption']] = relationship(
        order_by='CriterionOption.order', cascade='all, delete-orphan', lazy='selectin'
    )


class CriterionOption(IdMixin, Base):
    """Пункт чек-листа. Исключающий пункт снимает остальные и наоборот."""

    __tablename__ = 'eval_criterion_options'

    criterion_id: Mapped[int] = mapped_column(ForeignKey('eval_criteria.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(300))
    points: Mapped[Decimal] = mapped_column(Points)
    is_exclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)


class Sheet(IdMixin, TimestampMixin, Base):
    """Оценочный лист: работы, судьи и таблица оценок."""

    __tablename__ = 'eval_sheets'

    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey('event_stages.id', ondelete='SET NULL'))
    scorecard_id: Mapped[int] = mapped_column(ForeignKey('eval_scorecards.id', ondelete='RESTRICT'))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default='draft')  # draft | active | closed
    mode: Mapped[str] = mapped_column(String(20), default='jury')  # jury | anonymous | mixed
    aggregate: Mapped[str] = mapped_column(String(20), default='avg')  # avg | sum | median
    rank_method: Mapped[str] = mapped_column(String(20), default='competition')  # competition 1-1-3 | dense 1-1-2
    include_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scorecard: Mapped[Scorecard] = relationship(lazy='joined')
    judges: Mapped[list['SheetJudge']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    works: Mapped[list['SheetWork']] = relationship(
        order_by='SheetWork.order', cascade='all, delete-orphan', lazy='selectin', back_populates='sheet'
    )


class SheetJudge(IdMixin, Base):
    __tablename__ = 'eval_sheet_judges'
    __table_args__ = (UniqueConstraint('sheet_id', 'user_id'),)

    sheet_id: Mapped[int] = mapped_column(ForeignKey('eval_sheets.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    # Модератор может дать судье доступ к закрытому листу, если тот не успел к закрытию
    reopened: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')

    user: Mapped[User] = relationship(lazy='joined')


class SheetWork(IdMixin, Base):
    __tablename__ = 'eval_sheet_works'
    __table_args__ = (UniqueConstraint('sheet_id', 'application_id'),)

    sheet_id: Mapped[int] = mapped_column(ForeignKey('eval_sheets.id', ondelete='CASCADE'), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    public_token: Mapped[str] = mapped_column(String(64), unique=True)
    score: Mapped[Decimal | None] = mapped_column(Points)
    rank: Mapped[int | None] = mapped_column(Integer)
    is_scored: Mapped[bool] = mapped_column(Boolean, default=False)

    sheet: Mapped[Sheet] = relationship(back_populates='works')
    application: Mapped[Application] = relationship(lazy='joined')
    evaluations: Mapped[list['Evaluation']] = relationship(
        cascade='all, delete-orphan', lazy='selectin', back_populates='work'
    )


class Evaluation(IdMixin, TimestampMixin, Base):
    """Оценка работы одним судьёй или анонимным зрителем."""

    __tablename__ = 'eval_evaluations'
    __table_args__ = (UniqueConstraint('sheet_work_id', 'judge_id'),)

    sheet_work_id: Mapped[int] = mapped_column(ForeignKey('eval_sheet_works.id', ondelete='CASCADE'), index=True)
    judge_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    anonymous_name: Mapped[str] = mapped_column(String(100), default='')
    score: Mapped[Decimal | None] = mapped_column(Points)
    is_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    comment: Mapped[str] = mapped_column(Text, default='')

    work: Mapped[SheetWork] = relationship(back_populates='evaluations')
    judge: Mapped[User | None] = relationship(lazy='joined')
    items: Mapped[list['EvaluationItem']] = relationship(cascade='all, delete-orphan', lazy='selectin')


class EvaluationItem(IdMixin, Base):
    __tablename__ = 'eval_items'
    __table_args__ = (UniqueConstraint('evaluation_id', 'criterion_id'),)

    evaluation_id: Mapped[int] = mapped_column(ForeignKey('eval_evaluations.id', ondelete='CASCADE'), index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey('eval_criteria.id', ondelete='CASCADE'))
    level_id: Mapped[int | None] = mapped_column(ForeignKey('eval_scale_levels.id', ondelete='SET NULL'))
    score: Mapped[Decimal | None] = mapped_column(Points)
    comment: Mapped[str] = mapped_column(Text, default='')

    options: Mapped[list['EvaluationItemOption']] = relationship(cascade='all, delete-orphan', lazy='selectin')


class EvaluationItemOption(Base):
    __tablename__ = 'eval_item_options'

    item_id: Mapped[int] = mapped_column(ForeignKey('eval_items.id', ondelete='CASCADE'), primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey('eval_criterion_options.id', ondelete='CASCADE'), primary_key=True
    )
