"""Persistencia y enriquecimiento de actividades."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.models.activity import Activity, Lap, Record
from fitapp.services.fit_parser import ParsedFit
from fitapp.services.geocoding import generate_activity_name
from fitapp.services.power_estimation import build_power_series, compute_normalized_power


async def persist_activity(
    db: AsyncSession,
    user_id: uuid.UUID,
    parsed: ParsedFit,
    total_mass_kg: float = 85.0,
    streams_fetched: bool = True,
) -> tuple[Activity, bool]:
    """Persiste una actividad parseada. Devuelve (activity, is_duplicate).

    El geocoding NO se realiza aqui: se encola como tarea de fondo desde el
    endpoint de upload para no bloquear la respuesta HTTP.
    """
    result = await db.execute(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.file_hash == parsed.file_hash,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, True

    # Cross-source deduplication: Strava registra start_date con ~1s de diferencia
    # respecto al fichero FIT del mismo dispositivo → usamos ventana de ±60 s
    if parsed.started_at is not None:
        dup_result = await db.execute(
            select(Activity).where(
                Activity.user_id == user_id,
                Activity.started_at.between(
                    parsed.started_at - timedelta(seconds=60),
                    parsed.started_at + timedelta(seconds=60),
                ),
            )
        )
        existing_by_time = dup_result.scalar_one_or_none()
        if existing_by_time:
            return existing_by_time, True

    np_val: int | None = None
    if parsed.records:
        powers = build_power_series(parsed.records, total_mass_kg)
        np_val = compute_normalized_power(powers)

    activity = Activity(
        user_id=user_id,
        file_hash=parsed.file_hash,
        file_name=parsed.file_name,
        name=parsed.name,  # None para FIT (se enriquece por geocoding); valor real para Strava
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
        normalized_power=np_val,
        calories=parsed.calories,
        start_point=parsed.start_point_wkt,
        bbox=parsed.bbox_wkt,
        streams_fetched=streams_fetched,
    )
    db.add(activity)
    await db.flush()

    if parsed.records:
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


async def enrich_activity_name(
    db: AsyncSession,
    activity_id: uuid.UUID,
    force: bool = False,
) -> bool:
    """Geocodifica el nombre de una actividad a partir de sus records GPS.

    Si force=False (por defecto), solo actua cuando name IS NULL.
    Devuelve True si el nombre fue actualizado.
    """
    act_result = await db.execute(
        select(Activity).where(Activity.id == activity_id)
    )
    activity = act_result.scalar_one_or_none()
    if activity is None:
        return False
    if activity.name is not None and not force:
        return False

    rec_result = await db.execute(
        select(func.ST_AsGeoJSON(Record.position).label("geojson"))
        .where(Record.activity_id == activity_id, Record.position.isnot(None))
        .order_by(Record.ts)
    )
    records = []
    for row in rec_result.all():
        if row.geojson:
            coords = json.loads(row.geojson)["coordinates"]
            records.append({"lat": coords[1], "lon": coords[0]})

    name = await generate_activity_name(records)
    if name:
        activity.name = name
        await db.commit()
        return True
    return False


async def _enrich_name_bg(activity_id: uuid.UUID) -> None:
    """Tarea de fondo: crea su propia sesion y llama a enrich_activity_name.

    Se encola con BackgroundTasks tras cada upload exitoso y desde el endpoint
    POST /activities/enrich-names. Se puede mockear en tests con:
        patch("fitapp.services.activity_service._enrich_name_bg")
    """
    from fitapp.db import SessionLocal
    async with SessionLocal() as db:
        await enrich_activity_name(db, activity_id)


async def recalculate_np_for_user(
    user_id: uuid.UUID,
    total_mass_kg: float = 85.0,
) -> int:
    """Recalcula normalized_power para todas las actividades del usuario.

    Lee los records de cada actividad desde BD y recomputa NP usando el modelo
    físico o el medidor de potencia si existe. Devuelve el número de actividades
    actualizadas.
    """
    from fitapp.db import SessionLocal

    updated = 0
    async with SessionLocal() as db:
        result = await db.execute(select(Activity).where(Activity.user_id == user_id))
        activities = result.scalars().all()

        for act in activities:
            rec_result = await db.execute(
                select(
                    Record.speed_mps,
                    Record.altitude_m,
                    Record.distance_m,
                    Record.power,
                )
                .where(Record.activity_id == act.id)
                .order_by(Record.ts)
            )
            rows = rec_result.all()
            if not rows:
                continue

            records_list = [
                {
                    "speed_mps": row.speed_mps,
                    "altitude_m": row.altitude_m,
                    "distance_m": row.distance_m,
                    "power": row.power,
                }
                for row in rows
            ]
            powers = build_power_series(records_list, total_mass_kg)
            np_val = compute_normalized_power(powers)
            if np_val != act.normalized_power:
                act.normalized_power = np_val
                db.add(act)
                updated += 1

        await db.commit()
    return updated


async def _recalculate_np_bg(user_id: uuid.UUID, total_mass_kg: float = 85.0) -> None:
    """Tarea de fondo para recalcular NP. Llama a recalculate_np_for_user."""
    await recalculate_np_for_user(user_id, total_mass_kg)


async def enrich_activity_with_streams(
    db: AsyncSession,
    activity: Activity,
    streams: dict,
    laps_data: list[dict],
    total_mass_kg: float = 85.0,
) -> None:
    """Añade records y laps a una actividad Strava que fue importada sin streams (fase 1).

    Actualiza también start_point, bbox, avg_hr, max_hr, avg_cadence, avg_power,
    normalized_power y marca streams_fetched=True.
    """
    from fitapp.services.strava_service import parse_strava_records, parse_strava_laps, build_bbox_wkt

    records_data = parse_strava_records(activity.started_at, streams)
    laps_list = parse_strava_laps(laps_data)

    if records_data:
        seen_ts: set = set()
        for r in records_data:
            if r["ts"] not in seen_ts:
                seen_ts.add(r["ts"])
                db.add(Record(
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
                ))

        latlng_stream = streams.get("latlng", [])
        bbox_wkt = build_bbox_wkt(latlng_stream)
        if bbox_wkt:
            activity.bbox = bbox_wkt

        start_latlng = latlng_stream[0] if latlng_stream else None
        if start_latlng and activity.start_point is None:
            activity.start_point = f"POINT({start_latlng[1]} {start_latlng[0]})"

        powers = build_power_series(records_data, total_mass_kg)
        np_val = compute_normalized_power(powers)
        if np_val:
            activity.normalized_power = np_val

    if laps_list:
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
            for lap in laps_list
        ])

    activity.streams_fetched = True
    await db.commit()
