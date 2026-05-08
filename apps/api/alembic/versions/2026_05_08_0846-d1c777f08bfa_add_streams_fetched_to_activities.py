"""add_streams_fetched_to_activities

Revision ID: d1c777f08bfa
Revises: fa4b4510841b
Create Date: 2026-05-08 08:46:34.634119+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd1c777f08bfa'
down_revision: str | None = 'fa4b4510841b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('streams_fetched', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('activities', 'streams_fetched')
