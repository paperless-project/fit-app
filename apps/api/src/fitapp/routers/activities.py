"""Endpoints de actividades: listado, detalle, upload, edición y exportación."""
from __future__ import annotations

import csv
import io
import json
import math
import tempfile
import uuid
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.activity import Activity, Lap, Record
from fitapp.models.user import User
from fitapp.schemas.activity import ActivityDetailOut, ActivityOut, ActivityPage, ActivityPatch, LapOut, RecordOut
from fitapp.services.activity_service import _enrich_name_bg, enrich_activity_name, persist_activity
from fitapp.services.fit_parser import parse_fit_safe

router = APIRouter(prefix="/activities", tags=["activities"])


def _filter_stmt(stmt, user_id, q, sport, date_from, date_to):
    stmt = stmt.where(Activity.user_id == user_id)
    if q:
        stmt = stmt.where(Activity.name.ilike(f"%{q}%"))
    if sport:
        stmt = stmt.where(Activity.sport == sport)
    if date_from:
        stmt = stmt.where(Activity.started_at >= date_from)
    if date_to:
        stmt = stmt.where(Activity.started_at < date_to + timedelta(days=1))
    return stmt


@router.get("/", response_model=ActivityPage)
async def list_activities(
    q: str | None = Query(None, description="Buscar por nombre"),
    sport: str | None = Query(None, description="Filtrar por deporte"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> ActivityPage:
    stmt = _filter_stmt(select(Activity), user.id, q, sport, date_from, date_to)

    total: int = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * size
    items = list((await db.execute(stmt.order_by(Activity.started_at.desc()).offset(offset).limit(size))).scalars())
    pages = max(1, math.ceil(total / size)) if total else 1

    return ActivityPage(items=items, total=total, page=page, size=size, pages=pages)


@router.post("/upload", response_model=ActivityOut, status_code=201)
async def upload_activity(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> Activity:
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parsed, _ = parse_fit_safe(tmp_path)
        parsed.file_name = file.filename or tmp_path.name
    except Exception:
        raise HTTPException(status_code=400, detail="INVALID_FIT_FILE")
    finally:
        tmp_path.unlink(missing_ok=True)

    activity, is_duplicate = await persist_activity(db, user.id, parsed)
    if is_duplicate:
        raise HTTPException(status_code=409, detail="ACTIVITY_ALREADY_EXISTS")

    background_tasks.add_task(_enrich_name_bg, activity.id)
    return activity


@router.post("/enrich-names")
async def trigger_enrich_names(
    background_tasks: BackgroundTasks,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Encola geocodificacion de nombre para todas las actividades del usuario con name IS NULL."""
    result = await db.execute(
        select(Activity.id).where(Activity.user_id == user.id, Activity.name.is_(None))
    )
    ids = [row[0] for row in result.all()]
    for activity_id in ids:
        background_tasks.add_task(_enrich_name_bg, activity_id)
    return {"queued": len(ids)}


# IMPORTANTE: /sports y /export/csv deben estar registrados antes de /{activity_id}
@router.get("/sports")
async def list_sports(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> list[str]:
    """Deportes distintos del usuario, para poblar el desplegable de filtros."""
    result = await db.execute(
        select(Activity.sport)
        .where(Activity.user_id == user.id, Activity.sport.isnot(None))
        .distinct()
        .order_by(Activity.sport)
    )
    return [row[0] for row in result.all()]


# IMPORTANTE: /export/csv debe estar registrado antes de /{activity_id}
@router.get("/export/csv")
async def export_csv(
    q: str | None = Query(None),
    sport: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    stmt = _filter_stmt(select(Activity), user.id, q, sport, date_from, date_to)
    result = await db.execute(stmt.order_by(Activity.started_at.desc()))
    activities = list(result.scalars())

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "fecha", "nombre", "deporte", "distancia_km", "duracion_s",
        "moving_time_s", "desnivel_m", "vel_media_kmh", "fc_media", "calorias", "notas",
    ])
    for a in activities:
        writer.writerow([
            a.started_at.date().isoformat(),
            a.name or "",
            a.sport or "",
            round(float(a.distance_m) / 1000, 2) if a.distance_m else "",
            a.duration_s or "",
            a.moving_time_s or "",
            round(float(a.ascent_m), 0) if a.ascent_m else "",
            round(float(a.avg_speed_mps) * 3.6, 1) if a.avg_speed_mps else "",
            a.avg_hr or "",
            a.calories or "",
            a.notes or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=actividades.csv"},
    )


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
        return coords[1], coords[0]

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


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="ACTIVITY_NOT_FOUND")
    if activity.user_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    await db.delete(activity)
    await db.commit()


@router.patch("/{activity_id}", response_model=ActivityOut)
async def update_activity(
    activity_id: uuid.UUID,
    patch: ActivityPatch,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> Activity:
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="ACTIVITY_NOT_FOUND")

    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)

    await db.commit()
    await db.refresh(activity)
    return activity


@router.get("/{activity_id}/export/gpx")
async def export_gpx(
    activity_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    act_result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = act_result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="ACTIVITY_NOT_FOUND")

    rec_result = await db.execute(
        select(
            Record.ts,
            Record.altitude_m,
            Record.heart_rate,
            Record.cadence,
            Record.power,
            func.ST_AsGeoJSON(Record.position).label("geojson"),
        )
        .where(Record.activity_id == activity_id)
        .order_by(Record.ts)
    )
    rows = rec_result.all()

    gpx = ET.Element("gpx", {
        "version": "1.1",
        "creator": "fit-app",
        "xmlns": "http://www.topografix.com/GPX/1/1",
        "xmlns:gpxtpx": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
    })
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = activity.name or activity.file_name
    trkseg = ET.SubElement(trk, "trkseg")

    for row in rows:
        if not row.geojson:
            continue
        coords = json.loads(row.geojson)["coordinates"]
        trkpt = ET.SubElement(trkseg, "trkpt", {"lat": str(coords[1]), "lon": str(coords[0])})
        if row.altitude_m is not None:
            ET.SubElement(trkpt, "ele").text = str(float(row.altitude_m))
        ET.SubElement(trkpt, "time").text = row.ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if any(v is not None for v in (row.heart_rate, row.cadence, row.power)):
            tpe = ET.SubElement(ET.SubElement(trkpt, "extensions"), "gpxtpx:TrackPointExtension")
            if row.heart_rate is not None:
                ET.SubElement(tpe, "gpxtpx:hr").text = str(row.heart_rate)
            if row.cadence is not None:
                ET.SubElement(tpe, "gpxtpx:cad").text = str(row.cadence)
            if row.power is not None:
                ET.SubElement(tpe, "gpxtpx:power").text = str(row.power)

    buf = io.BytesIO()
    ET.ElementTree(gpx).write(buf, encoding="utf-8", xml_declaration=True)
    buf.seek(0)

    safe_name = (activity.name or activity.file_name).replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.gpx"},
    )
