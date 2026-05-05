"""Endpoints de actividades: listado y upload."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.activity import Activity
from fitapp.models.user import User
from fitapp.schemas.activity import ActivityOut
from fitapp.services.activity_service import persist_activity
from fitapp.services.fit_parser import parse_fit_safe

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/", response_model=list[ActivityOut])
async def list_activities(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> list[Activity]:
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at.desc())
    )
    return list(result.scalars())


@router.post("/upload", response_model=ActivityOut, status_code=201)
async def upload_activity(
    file: UploadFile = File(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> Activity:
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parsed, repaired = parse_fit_safe(tmp_path)
        parsed.file_name = file.filename or tmp_path.name
    except Exception:
        raise HTTPException(status_code=400, detail="INVALID_FIT_FILE")
    finally:
        tmp_path.unlink(missing_ok=True)

    activity, is_duplicate = await persist_activity(db, user.id, parsed)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="ACTIVITY_ALREADY_EXISTS")

    return activity
