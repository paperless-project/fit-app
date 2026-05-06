"""Endpoints de estadísticas agregadas."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.activity import Activity
from fitapp.models.user import User
from fitapp.schemas.stats import CalendarDay, CalendarResponse, StatsSummary, TimelineEntry

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
