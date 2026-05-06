"""Modelo User compatible con fastapi-users."""
from __future__ import annotations

import uuid

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID, SQLAlchemyBaseUserTableUUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from fitapp.db import Base


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
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship("OAuthAccount", lazy="joined")
