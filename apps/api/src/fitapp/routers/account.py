"""Endpoints de gestión de cuenta: cambio de contraseña y borrado de cuenta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import UserManager, current_active_user, get_user_manager
from fitapp.db import get_session
from fitapp.models.activity import Activity
from fitapp.models.user import User
from fitapp.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["account"])


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La nueva contraseña debe tener al menos 8 caracteres")
        return v


class DeleteAccountBody(BaseModel):
    confirm: bool


@router.patch("/me/password", status_code=200)
async def change_password(
    body: PasswordChange,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> dict:
    valid, _ = user_manager.password_helper.verify_and_update(
        body.current_password, user.hashed_password
    )
    if not valid:
        raise HTTPException(status_code=400, detail="INVALID_CURRENT_PASSWORD")
    hashed = user_manager.password_helper.hash(body.new_password)
    await user_manager.user_db.update(user, {"hashed_password": hashed})
    return {"detail": "PASSWORD_CHANGED"}


class TrainingProfile(BaseModel):
    ftp: int | None = None
    weight_kg: float | None = None

    @field_validator("ftp")
    @classmethod
    def validate_ftp(cls, v: int | None) -> int | None:
        if v is not None and not (50 <= v <= 600):
            raise ValueError("El FTP debe estar entre 50 y 600 W")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float | None) -> float | None:
        if v is not None and not (30.0 <= v <= 250.0):
            raise ValueError("El peso debe estar entre 30 y 250 kg")
        return v


@router.patch("/me/training", response_model=UserRead, status_code=200)
async def update_training_profile(
    body: TrainingProfile,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> User:
    if body.ftp is not None:
        user.ftp = body.ftp
    if body.weight_kg is not None:
        user.weight_kg = body.weight_kg  # type: ignore[assignment]
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/me", status_code=204)
async def delete_account(
    body: DeleteAccountBody,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
    db: AsyncSession = Depends(get_session),
) -> None:
    if not body.confirm:
        raise HTTPException(status_code=400, detail="CONFIRMATION_REQUIRED")
    await db.execute(delete(Activity).where(Activity.user_id == user.id))
    await db.commit()
    await user_manager.delete(user)
