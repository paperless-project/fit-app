"""Modelo User compatible con fastapi-users."""
from __future__ import annotations

import datetime
import enum
import uuid

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID, SQLAlchemyBaseUserTableUUID
from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from fitapp.db import Base


class Gender(str, enum.Enum):
    hombre = "hombre"
    mujer = "mujer"
    no_binario = "no_binario"
    prefiero_no_decirlo = "prefiero_no_decirlo"
    otro = "otro"


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    # La base genera FK a "user.id" pero nuestra tabla se llama "users"
    @declared_attr  # type: ignore[override]
    def user_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False
        )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    # SQLAlchemyBaseUserTableUUID ya define id (UUID), email, hashed_password,
    # is_active, is_superuser, is_verified.
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined", cascade="all, delete-orphan"
    )

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(Gender, name="gender_enum"), nullable=True
    )
