"""Убраны лендинги; заявка в два шага: общая заявка, затем анкета в кабинете

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-05 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('site_domains')
    op.drop_constraint(op.f('fk_sites_published_version_id_site_versions'), 'sites', type_='foreignkey')
    op.drop_table('site_versions')
    op.drop_table('sites')
    # Модуль лендинга больше не существует
    op.execute("UPDATE events SET modules = modules - 'landing'")

    op.add_column('events', sa.Column('details_closes_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('events', sa.Column('webhook_token', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_events_webhook_token', 'events', ['webhook_token'])

    op.alter_column('applications', 'user_id', existing_type=sa.BigInteger(), nullable=True)
    for name, length in (
        ('contact_name', 300),
        ('contact_email', 255),
        ('contact_phone', 40),
        ('contact_organization', 300),
        ('contact_grade', 20),
    ):
        op.add_column('applications', sa.Column(name, sa.String(length=length), server_default='', nullable=False))
    op.create_index('ix_applications_contact_email', 'applications', ['contact_email'])
    op.add_column('applications', sa.Column('source', sa.String(length=20), server_default='cabinet', nullable=False))
    op.add_column('applications', sa.Column('external_id', sa.String(length=100), nullable=True))
    op.add_column(
        'applications',
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    )
    op.add_column('applications', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_applications_event_id_external_id', 'applications', ['event_id', 'external_id'])

    # Существующие заявки уже прошли первый шаг. Перенесённые из NocoBase принадлежат архивной учётной записи.
    op.execute('UPDATE applications SET confirmed_at = created_at')
    op.execute(
        """
        UPDATE applications AS a SET source = 'import'
        FROM users AS u
        WHERE u.id = a.user_id AND u.email = 'archive@import.sk-events.local'
        """
    )
    op.execute(
        """
        UPDATE applications AS a SET contact_email = u.email
        FROM users AS u
        WHERE u.id = a.user_id AND a.source != 'import'
        """
    )


def downgrade() -> None:
    # Открытые заявки без учётной записи не могут существовать в прежней схеме
    op.execute('DELETE FROM applications WHERE user_id IS NULL')
    op.drop_constraint('uq_applications_event_id_external_id', 'applications', type_='unique')
    op.drop_column('applications', 'confirmed_at')
    op.drop_column('applications', 'raw_payload')
    op.drop_column('applications', 'external_id')
    op.drop_column('applications', 'source')
    op.drop_index('ix_applications_contact_email', table_name='applications')
    for name in ('contact_grade', 'contact_organization', 'contact_phone', 'contact_email', 'contact_name'):
        op.drop_column('applications', name)
    op.execute("UPDATE applications SET status = 'draft' WHERE status = 'requested'")
    op.alter_column('applications', 'user_id', existing_type=sa.BigInteger(), nullable=False)

    op.drop_constraint('uq_events_webhook_token', 'events', type_='unique')
    op.drop_column('events', 'webhook_token')
    op.drop_column('events', 'details_closes_at')

    # Таблицы лендингов восстанавливаются пустыми, их содержимое не возвращается
    op.create_table(
        'sites',
        sa.Column('event_id', sa.BigInteger(), nullable=False),
        sa.Column('draft', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('published_version_id', sa.BigInteger(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.BigInteger(), server_default=sa.text('next_id()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_sites_event_id_events'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_sites')),
        sa.UniqueConstraint('event_id', name=op.f('uq_sites_event_id')),
    )
    op.create_table(
        'site_versions',
        sa.Column('site_id', sa.BigInteger(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('note', sa.String(length=200), server_default='', nullable=False),
        sa.Column('created_by_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.BigInteger(), server_default=sa.text('next_id()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_id'], ['users.id'], name=op.f('fk_site_versions_created_by_id_users'), ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['site_id'], ['sites.id'], name=op.f('fk_site_versions_site_id_sites'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_site_versions')),
        sa.UniqueConstraint('site_id', 'number', name=op.f('uq_site_versions_site_id')),
    )
    op.create_index(op.f('ix_site_versions_site_id'), 'site_versions', ['site_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_sites_published_version_id_site_versions'),
        'sites',
        'site_versions',
        ['published_version_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_table(
        'site_domains',
        sa.Column('site_id', sa.BigInteger(), nullable=False),
        sa.Column('domain', sa.String(length=253), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), server_default='', nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.BigInteger(), server_default=sa.text('next_id()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_site_domains_site_id_sites'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_site_domains')),
        sa.UniqueConstraint('domain', name=op.f('uq_site_domains_domain')),
    )
    op.create_index(op.f('ix_site_domains_site_id'), 'site_domains', ['site_id'], unique=False)
