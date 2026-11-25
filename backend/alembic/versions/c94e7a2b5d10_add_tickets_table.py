"""add tickets table

Revision ID: c94e7a2b5d10
Revises: b81d4f6a2c93
Create Date: 2026-11-25 18:05:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from alembic import op

revision: str = 'c94e7a2b5d10'
down_revision: str | None = 'b81d4f6a2c93'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'tickets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('raw_message', sa.Text(), nullable=False),
        sa.Column('product_name', sa.String(length=160), nullable=True),
        sa.Column(
            'status',
            sa.Enum('open', 'escalated', 'resolved', 'dismissed', name='ticketstatus', native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('urgency', sa.String(length=16), nullable=False),
        sa.Column('sentiment', sa.String(length=16), nullable=False),
        sa.Column('needs_human', sa.Boolean(), nullable=False),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('suggested_reply', sa.Text(), nullable=True),
        sa.Column('extracted_data', pg.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('triage_latency_ms', sa.Integer(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tickets')),
    )
    op.create_index(op.f('ix_tickets_created_by'), 'tickets', ['created_by'])
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'])
    op.create_index(op.f('ix_tickets_urgency'), 'tickets', ['urgency'])
    op.create_index(op.f('ix_tickets_needs_human'), 'tickets', ['needs_human'])


def downgrade() -> None:
    op.drop_index(op.f('ix_tickets_needs_human'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_urgency'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_created_by'), table_name='tickets')
    op.drop_table('tickets')
