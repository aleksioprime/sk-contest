"""Убран тип мероприятия: разделы выбираются при создании

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-06 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('events', 'type')


def downgrade() -> None:
    op.add_column(
        'events', sa.Column('type', sa.String(length=30), server_default='project_contest', nullable=False)
    )
    op.alter_column('events', 'type', server_default=None)
