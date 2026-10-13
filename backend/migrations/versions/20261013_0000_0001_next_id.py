"""Функция next_id() для первичных ключей

ID = (миллисекунды с 2020-01-01 << 12) | (nextval % 4096).
41 бит времени + 12 бит счётчика = 53 бита: число безопасно для JavaScript до 2089 года.
Эпоха раньше, чем у NocoBase, поэтому новые ID всегда больше перенесённых.

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE SEQUENCE IF NOT EXISTS global_id_seq')
    op.execute(
        """
        CREATE OR REPLACE FUNCTION next_id() RETURNS bigint
        LANGUAGE plpgsql AS $$
        DECLARE
            epoch_ms CONSTANT bigint := 1577836800000;
            now_ms bigint;
            seq bigint;
        BEGIN
            seq := nextval('global_id_seq') % 4096;
            now_ms := floor(extract(epoch FROM clock_timestamp()) * 1000);
            RETURN ((now_ms - epoch_ms) << 12) | seq;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute('DROP FUNCTION IF EXISTS next_id()')
    op.execute('DROP SEQUENCE IF EXISTS global_id_seq')
