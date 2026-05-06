"""Endpoints de actividades: listado, detalle y upload."""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.activity import Activity, Lap, Record
from fitapp.models.user import User
from fitapp.schemas.activity import ActivityDetailOut, ActivityOut, LapOut, RecordOut
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


@router.get("/{activity_id}", response_model=ActivityDetailOut)
async def get_activity_detail(
    activity_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> ActivityDetailOut:
    act_result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = act_result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="ACTIVITY_NOT_FOUND")

    # Records con lat/lon extraidos via ST_AsGeoJSON (acepta geography directamente)
    rec_result = await db.execute(
        select(
            Record.ts,
            Record.altitude_m,
            Record.distance_m,
            Record.speed_mps,
            Record.heart_rate,
            Record.cadence,
            Record.power,
            func.ST_AsGeoJSON(Record.position).label("geojson"),
        )
        .where(Record.activity_id == activity_id)
        .order_by(Record.ts)
    )

    def _parse_point(geojson_str: str | None) -> tuple[float | None, float | None]:
        if not geojson_str:
            return None, None
        coords = json.loads(geojson_str)["coordinates"]
        return coords[1], coords[0]  # lat, lon

    records = []
    for row in rec_result.all():
        lat, lon = _parse_point(row.geojson)
        records.append(RecordOut(
            ts=row.ts,
            lat=lat,
            lon=lon,
            altitude_m=row.altitude_m,
            distance_m=row.distance_m,
            speed_mps=row.speed_mps,
            heart_rate=row.heart_rate,
            cadence=row.cadence,
            power=row.power,
        ))

    lap_result = await db.execute(
        select(Lap).where(Lap.activity_id == activity_id).order_by(Lap.lap_index)
    )
    laps = [LapOut.model_validate(lap) for lap in lap_result.scalars()]

    return ActivityDetailOut(
        **ActivityOut.model_validate(activity).model_dump(),
        records=records,
        laps=laps,
    )


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
