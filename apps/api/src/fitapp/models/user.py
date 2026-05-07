"""Modelo User compatible con fastapi-users."""
from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID, SQLAlchemyBaseUserTableUUID
from sqlalchemy import BigInteger, Date, Enum as SAEnum, ForeignKey, Integer, Numeric, String
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
    ftp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)


class StravaToken(Base):
    __tablename__ = "strava_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)  # epoch Unix
    athlete_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_import_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
