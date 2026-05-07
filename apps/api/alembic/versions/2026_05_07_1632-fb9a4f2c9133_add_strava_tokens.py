"""add_strava_tokens

Revision ID: fb9a4f2c9133
Revises: fa3c8e7b1d2a
Create Date: 2026-05-07 16:32:19.098222+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'fb9a4f2c9133'
down_revision: str | None = 'fa3c8e7b1d2a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('strava_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('access_token', sa.String(length=255), nullable=False),
    sa.Column('refresh_token', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.Column('athlete_id', sa.BigInteger(), nullable=True),
    sa.Column('last_import_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('strava_tokens')
