"""Schemas Pydantic para los endpoints de estadísticas."""
from __future__ import annotations

from pydantic import BaseModel


class StatsSummary(BaseModel):
    total_activities: int
    total_km: float
    total_hours: float
    total_ascent_m: float


class CalendarDay(BaseModel):
    count: int
    km: float


class CalendarResponse(BaseModel):
    year: int
    days: dict[str, CalendarDay]


class TimelineEntry(BaseModel):
    period: str
    count: int
    km: float
    hours: float
    ascent_m: float


# ── Calendario detallado con semanas ─────────────────────────────────────────

class YearSummary(BaseModel):
    total_activities: int
    total_km: float
    total_hours: float
    total_calories: int


class CalendarActivity(BaseModel):
    id: str
    name: str | None
    sport: str | None
    distance_m: float | None
    duration_s: int | None
    calories: int | None
    avg_power: int | None
    normalized_power: int | None
    tss: float | None
    intensity_factor: float | None


class WeekSummary(BaseModel):
    week_number: int
    week_start: str          # ISO YYYY-MM-DD (lunes)
    distance_m: float
    duration_s: int
    calories: int
    tss: float
    intensity_factor: float | None


class CalendarDetailResponse(BaseModel):
    year: int
    ftp: int
    summary: YearSummary
    weeks: list[WeekSummary]
    days: dict[str, list[CalendarActivity]]  # clave: YYYY-MM-DD
