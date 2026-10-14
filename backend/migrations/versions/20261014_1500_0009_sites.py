"""Конструктор лендингов: сайты, версии публикаций, свои домены

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_site_versions_created_by_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_site_versions_site_id_sites'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_site_versions')),
        sa.UniqueConstraint('site_id', 'number', name=op.f('uq_site_versions_site_id')),
    )
    op.create_index(op.f('ix_site_versions_site_id'), 'site_versions', ['site_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_sites_published_version_id_site_versions'), 'sites', 'site_versions',
        ['published_version_id'], ['id'], ondelete='SET NULL',
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


def downgrade() -> None:
    op.drop_index(op.f('ix_site_domains_site_id'), table_name='site_domains')
    op.drop_table('site_domains')
    op.drop_constraint(op.f('fk_sites_published_version_id_site_versions'), 'sites', type_='foreignkey')
    op.drop_index(op.f('ix_site_versions_site_id'), table_name='site_versions')
    op.drop_table('site_versions')
    op.drop_table('sites')
