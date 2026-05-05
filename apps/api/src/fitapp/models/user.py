"""Modelo User compatible con fastapi-users."""
from __future__ import annotations

import uuid

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column

from fitapp.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    # SQLAlchemyBaseUserTableUUID ya define id (UUID), email, hashed_password,
    # is_active, is_superuser, is_verified.
