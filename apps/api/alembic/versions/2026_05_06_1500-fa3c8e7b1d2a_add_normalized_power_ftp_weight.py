"""add normalized_power to activities and ftp weight_kg to users

Revision ID: fa3c8e7b1d2a
Revises: 159b99c22872
Create Date: 2026-05-06 15:00:00.000000+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "fa3c8e7b1d2a"
down_revision: str | None = "159b99c22872"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("normalized_power", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("ftp", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "weight_kg")
    op.drop_column("users", "ftp")
    op.drop_column("activities", "normalized_power")
