"""add activity name

Revision ID: 6bf7f63a1065
Revises: 379c3241c147
Create Date: 2026-05-05 11:57:45.009693+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '6bf7f63a1065'
down_revision: str | None = '379c3241c147'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'name')
