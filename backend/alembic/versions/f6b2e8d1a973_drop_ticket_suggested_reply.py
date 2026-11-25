"""drop tickets.suggested_reply

Revision ID: f6b2e8d1a973
Revises: e7a1c9d4f826
Create Date: 2026-11-25 20:10:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f6b2e8d1a973'
down_revision: str | None = 'e7a1c9d4f826'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_column('tickets', 'suggested_reply')


def downgrade() -> None:
    op.add_column(
        'tickets',
        sa.Column('suggested_reply', sa.Text(), nullable=True),
    )
