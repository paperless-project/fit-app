"""add_strava_import_status

Revision ID: fa4b4510841b
Revises: fb9a4f2c9133
Create Date: 2026-05-08 08:10:38.001151+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'fa4b4510841b'
down_revision: str | None = 'fb9a4f2c9133'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('strava_tokens', sa.Column('import_status', sa.String(length=32), nullable=True))
    op.add_column('strava_tokens', sa.Column('import_status_message', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('strava_tokens', 'import_status_message')
    op.drop_column('strava_tokens', 'import_status')
