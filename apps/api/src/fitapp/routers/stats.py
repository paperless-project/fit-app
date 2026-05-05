"""Endpoints de estadisticas agregadas. (esqueleto - se completa en Fase 5)"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from fitapp.auth.users import current_active_user
from fitapp.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
async def summary(user: User = Depends(current_active_user)) -> dict:
    # TODO Fase 5: agregar km, horas, desnivel del usuario
    return {"total_km": 0, "total_hours": 0, "total_activities": 0}
