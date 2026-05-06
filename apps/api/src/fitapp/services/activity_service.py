"""Persistencia de actividades parseadas."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.models.activity import Activity, Lap, Record
from fitapp.services.fit_parser import ParsedFit
from fitapp.services.geocoding import generate_activity_name


async def persist_activity(
    db: AsyncSession,
    user_id: uuid.UUID,
    parsed: ParsedFit,
) -> tuple[Activity, bool]:
    """Persiste una actividad parseada. Devuelve (activity, is_duplicate)."""
    result = await db.execute(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.file_hash == parsed.file_hash,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, True

    name = await generate_activity_name(parsed.records)

    activity = Activity(
        user_id=user_id,
        file_hash=parsed.file_hash,
        file_name=parsed.file_name,
        name=name,
        sport=parsed.sport,
        started_at=parsed.started_at,
        duration_s=parsed.duration_s,
        moving_time_s=parsed.moving_time_s,
        distance_m=parsed.distance_m,
        ascent_m=parsed.ascent_m,
        descent_m=parsed.descent_m,
        avg_speed_mps=parsed.avg_speed_mps,
        max_speed_mps=parsed.max_speed_mps,
        avg_hr=parsed.avg_hr,
        max_hr=parsed.max_hr,
        avg_cadence=parsed.avg_cadence,
        avg_power=parsed.avg_power,
        calories=parsed.calories,
        start_point=parsed.start_point_wkt,
        bbox=parsed.bbox_wkt,
    )
    db.add(activity)
    await db.flush()  # obtener activity.id antes de insertar hijos

    if parsed.records:
        # Algunos dispositivos Garmin repiten el mismo timestamp; deduplicar por ts
        seen_ts: set = set()
        unique_records = []
        for r in parsed.records:
            if r["ts"] not in seen_ts:
                seen_ts.add(r["ts"])
                unique_records.append(r)

        db.add_all([
            Record(
                activity_id=activity.id,
                ts=r["ts"],
                position=f"POINT({r['lon']} {r['lat']})" if r["lat"] is not None else None,
                altitude_m=r.get("altitude_m"),
                distance_m=r.get("distance_m"),
                speed_mps=r.get("speed_mps"),
                heart_rate=r.get("heart_rate"),
                cadence=r.get("cadence"),
                power=r.get("power"),
                temperature=r.get("temperature"),
            )
            for r in unique_records
        ])

    if parsed.laps:
        db.add_all([
            Lap(
                activity_id=activity.id,
                lap_index=lap["lap_index"],
                start_time=lap["start_time"],
                duration_s=lap.get("duration_s"),
                distance_m=lap.get("distance_m"),
                avg_speed_mps=lap.get("avg_speed_mps"),
                avg_hr=lap.get("avg_hr"),
                ascent_m=lap.get("ascent_m"),
            )
            for lap in parsed.laps
        ])

    await db.commit()
    await db.refresh(activity)
    return activity, False
