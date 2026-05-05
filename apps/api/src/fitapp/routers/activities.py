"""Endpoints CRUD y upload de actividades. (esqueleto - se completa en Fase 2)"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from fitapp.auth.users import current_active_user
from fitapp.models.user import User

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/")
async def list_activities(user: User = Depends(current_active_user)) -> list[dict]:
    # TODO Fase 2: leer de BD filtrando por user.id
    return []
