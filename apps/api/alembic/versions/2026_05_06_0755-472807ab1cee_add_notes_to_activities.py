"""add_notes_to_activities

Revision ID: 472807ab1cee
Revises: 6bf7f63a1065
Create Date: 2026-05-06 07:55:08.298143+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '472807ab1cee'
down_revision: str | None = '6bf7f63a1065'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'notes')
