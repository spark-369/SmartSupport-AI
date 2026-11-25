"""ticket chat origin (conversation_id, source_message_id)

Revision ID: e7a1c9d4f826
Revises: c94e7a2b5d10
Create Date: 2026-11-25 19:20:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = 'e7a1c9d4f826'
down_revision: str | None = 'c94e7a2b5d10'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        'tickets',
        sa.Column('conversation_id', sa.Uuid(), nullable=True),
    )
    op.add_column(
        'tickets',
        sa.Column('source_message_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_tickets_conversation_id_conversations',
        'tickets',
        'conversations',
        ['conversation_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_tickets_source_message_id_messages',
        'tickets',
        'messages',
        ['source_message_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_tickets_conversation_id', 'tickets', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('ix_tickets_conversation_id', table_name='tickets')
    op.drop_constraint('fk_tickets_source_message_id_messages', 'tickets', type_='foreignkey')
    op.drop_constraint('fk_tickets_conversation_id_conversations', 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'source_message_id')
    op.drop_column('tickets', 'conversation_id')
