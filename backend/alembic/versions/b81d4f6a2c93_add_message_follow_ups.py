"""add message follow_ups

Revision ID: b81d4f6a2c93
Revises: 042287eafe7e
Create Date: 2026-11-25 16:40:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b81d4f6a2c93'
down_revision: str | None = '042287eafe7e'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column(
            'follow_ups',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('messages', 'follow_ups')
