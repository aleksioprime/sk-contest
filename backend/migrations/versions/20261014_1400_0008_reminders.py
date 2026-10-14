"""Напоминания о черновиках заявок и о дедлайне оценочного листа

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('eval_sheet_judges', sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('eval_sheet_judges', 'reminded_at')
    op.drop_column('applications', 'reminded_at')
