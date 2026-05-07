"""Esquemas Pydantic de User para fastapi-users."""
from __future__ import annotations

import datetime
import uuid

from fastapi_users import schemas

from fitapp.models.user import Gender


class UserRead(schemas.BaseUser[uuid.UUID]):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: datetime.date | None = None
    gender: Gender | None = None
    ftp: int | None = None
    weight_kg: float | None = None

    model_config = {"from_attributes": True}


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: datetime.date | None = None
    gender: Gender | None = None
    ftp: int | None = None
    weight_kg: float | None = None
