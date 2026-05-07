"""Endpoints de estadísticas agregadas."""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.activity import Activity
from fitapp.models.user import User
from fitapp.schemas.stats import (
    CalendarActivity,
    CalendarDay,
    CalendarDetailResponse,
    CalendarResponse,
    StatsSummary,
    TimelineEntry,
    WeekSummary,
    YearSummary,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
async def summary(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> StatsSummary:
    result = await session.execute(
        select(
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.distance_m), 0),
            func.coalesce(func.sum(Activity.duration_s), 0),
            func.coalesce(func.sum(Activity.ascent_m), 0),
        ).where(Activity.user_id == user.id)
    )
    count, total_distance, total_duration, total_ascent = result.one()
    return StatsSummary(
        total_activities=int(count),
        total_km=float(total_distance) / 1000,
        total_hours=float(total_duration) / 3600,
        total_ascent_m=float(total_ascent),
    )


@router.get("/calendar", response_model=CalendarResponse)
async def calendar(
    year: int = Query(ge=2000, le=2100),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarResponse:
    result = await session.execute(
        select(
            func.date_trunc("day", Activity.started_at).label("day"),
            func.count(Activity.id).label("count"),
            func.coalesce(func.sum(Activity.distance_m), 0).label("distance"),
        )
        .where(
            Activity.user_id == user.id,
            extract("year", Activity.started_at) == year,
        )
        .group_by("day")
        .order_by("day")
    )
    rows = result.all()
    return CalendarResponse(
        year=year,
        days={
            row.day.date().isoformat(): CalendarDay(
                count=row.count,
                km=float(row.distance) / 1000,
            )
            for row in rows
        },
    )


@router.get("/timeline", response_model=list[TimelineEntry])
async def timeline(
    bucket: Literal["month", "year"] = Query(default="month"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[TimelineEntry]:
    trunc = "month" if bucket == "month" else "year"
    result = await session.execute(
        select(
            func.date_trunc(trunc, Activity.started_at).label("period"),
            func.count(Activity.id).label("count"),
            func.coalesce(func.sum(Activity.distance_m), 0).label("distance"),
            func.coalesce(func.sum(Activity.duration_s), 0).label("duration"),
            func.coalesce(func.sum(Activity.ascent_m), 0).label("ascent"),
        )
        .where(Activity.user_id == user.id)
        .group_by("period")
        .order_by("period")
    )
    rows = result.all()
    return [
        TimelineEntry(
            period=row.period.date().isoformat()[:7] if bucket == "month" else str(row.period.year),
            count=row.count,
            km=float(row.distance) / 1000,
            hours=float(row.duration) / 3600,
            ascent_m=float(row.ascent),
        )
        for row in rows
    ]


@router.get("/calendar-detail", response_model=CalendarDetailResponse)
async def calendar_detail(
    year: int = Query(ge=2000, le=2100),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarDetailResponse:
    """Calendario detallado: actividades por día + resumen por semana con TSS e IF."""
    ftp = user.ftp or 200

    result = await session.execute(
        select(Activity)
        .where(
            Activity.user_id == user.id,
            extract("year", Activity.started_at) == year,
        )
        .order_by(Activity.started_at)
    )
    activities = result.scalars().all()

    days: dict[str, list[CalendarActivity]] = {}
    # clave: (iso_year, iso_week) → datos acumulados
    weeks_data: dict[tuple[int, int], dict] = {}

    for act in activities:
        day_str = act.started_at.date().isoformat()
        np_val = act.normalized_power
        duration = act.duration_s or 0

        if np_val is not None and ftp > 0 and duration > 0:
            if_val = np_val / ftp
            tss_val = (duration * np_val * np_val) / (ftp * ftp * 36.0)
        else:
            if_val = None
            tss_val = None

        day_act = CalendarActivity(
            id=str(act.id),
            name=act.name,
            sport=act.sport,
            distance_m=float(act.distance_m) if act.distance_m is not None else None,
            duration_s=act.duration_s,
            calories=act.calories,
            avg_power=act.avg_power,
            normalized_power=np_val,
            tss=tss_val,
            intensity_factor=if_val,
        )
        days.setdefault(day_str, []).append(day_act)

        # Semana ISO: usar el lunes de la semana como clave
        dow = act.started_at.weekday()  # 0=lunes
        week_monday = act.started_at.date() - timedelta(days=dow)
        iso = act.started_at.date().isocalendar()
        week_key = (iso.year, iso.week)

        if week_key not in weeks_data:
            weeks_data[week_key] = {
                "week_number": iso.week,
                "week_start": week_monday.isoformat(),
                "distance_m": 0.0,
                "duration_s": 0,
                "calories": 0,
                "tss": 0.0,
                "np2_x_dur": 0.0,
                "total_dur_with_np": 0,
            }
        w = weeks_data[week_key]
        w["distance_m"] += float(act.distance_m or 0)
        w["duration_s"] += duration
        w["calories"] += act.calories or 0
        if tss_val is not None:
            w["tss"] += tss_val
        if np_val is not None and duration > 0:
            w["np2_x_dur"] += float(np_val) ** 2 * duration
            w["total_dur_with_np"] += duration

    # Ordenar semanas cronológicamente
    week_list: list[WeekSummary] = []
    for (_, _wk), w in sorted(weeks_data.items()):
        np2_x_dur = w["np2_x_dur"]
        total_dur_with_np = w["total_dur_with_np"]
        if total_dur_with_np > 0 and np2_x_dur > 0 and ftp > 0:
            weekly_if: float | None = math.sqrt(np2_x_dur / total_dur_with_np) / ftp
        else:
            weekly_if = None

        week_list.append(WeekSummary(
            week_number=w["week_number"],
            week_start=w["week_start"],
            distance_m=w["distance_m"],
            duration_s=w["duration_s"],
            calories=w["calories"],
            tss=w["tss"],
            intensity_factor=weekly_if,
        ))

    total_km = sum(float(a.distance_m or 0) for a in activities) / 1000
    total_hours = sum(a.duration_s or 0 for a in activities) / 3600
    total_calories = sum(a.calories or 0 for a in activities)

    return CalendarDetailResponse(
        year=year,
        ftp=ftp,
        summary=YearSummary(
            total_activities=len(activities),
            total_km=total_km,
            total_hours=total_hours,
            total_calories=total_calories,
        ),
        weeks=week_list,
        days=days,
    )


@router.post("/recalculate-np", status_code=202)
async def recalculate_np(
    background_tasks: BackgroundTasks,
    user: User = Depends(current_active_user),
) -> dict:
    """Recalcula el Normalized Power de todas las actividades del usuario en segundo plano."""
    from fitapp.services.activity_service import _recalculate_np_bg

    weight_kg = float(user.weight_kg) if user.weight_kg is not None else 75.0
    total_mass_kg = weight_kg + 10.0  # peso ciclista + bicicleta

    background_tasks.add_task(_recalculate_np_bg, user.id, total_mass_kg)
    return {"message": "Recalculando Normalized Power en segundo plano"}
