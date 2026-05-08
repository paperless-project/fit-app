"""Cliente Strava API + conversión de actividades a ParsedFit."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from fitapp.config import settings
from fitapp.services.fit_parser import ParsedFit

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"
SCOPE = "activity:read_all"

STREAM_KEYS = "time,latlng,altitude,heartrate,cadence,watts,temp,distance,velocity_smooth"


class StravaRateLimitError(Exception):
    """HTTP 429 de Strava: límite de peticiones alcanzado."""

    def __init__(self, retry_after: int, is_daily: bool) -> None:
        self.retry_after = retry_after
        self.is_daily = is_daily
        super().__init__(f"rate_limited retry_after={retry_after}s daily={is_daily}")


def _is_daily_limit(headers: Any, retry_after: int) -> bool:
    """Detecta si el 429 es por límite diario en vez de ventana de 15 min."""
    try:
        usage = headers.get("X-RateLimit-Usage", "").split(",")
        limit = headers.get("X-RateLimit-Limit", "600,30000").split(",")
        return int(usage[1].strip()) >= int(limit[1].strip())
    except (IndexError, ValueError, AttributeError):
        return retry_after > 960  # heurística: >16 min → límite diario


def get_authorization_url(state: str) -> str:
    redirect_uri = f"{settings.api_url}/strava/callback"
    return (
        f"{STRAVA_AUTH_URL}"
        f"?client_id={settings.strava_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&approval_prompt=auto"
        f"&scope={SCOPE}"
        f"&state={state}"
    )


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(STRAVA_TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(STRAVA_TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()


def is_token_expired(expires_at: int) -> bool:
    return time.time() >= expires_at - 60


async def get_valid_access_token(db: Any, user_id: Any) -> str:
    from fastapi import HTTPException
    from sqlalchemy import select
    from fitapp.models.user import StravaToken

    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user_id))
    token_row = result.scalar_one_or_none()
    if token_row is None:
        raise HTTPException(status_code=401, detail="Strava no conectado")

    if is_token_expired(token_row.expires_at):
        data = await refresh_access_token(token_row.refresh_token)
        token_row.access_token = data["access_token"]
        token_row.refresh_token = data["refresh_token"]
        token_row.expires_at = data["expires_at"]
        await db.commit()

    return token_row.access_token


async def _get(access_token: str, url: str, params: dict | None = None) -> httpx.Response:
    """GET autenticado. Lanza StravaRateLimitError en 429 para que el llamador gestione la espera."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        r = await client.get(url, params=params)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 900))
        raise StravaRateLimitError(retry_after, _is_daily_limit(r.headers, retry_after))
    return r


async def list_activities(
    access_token: str,
    after: int | None = None,
    before: int | None = None,
    page: int = 1,
    per_page: int = 100,
) -> list[dict]:
    params: dict[str, Any] = {"page": page, "per_page": per_page}
    if after:
        params["after"] = after
    if before:
        params["before"] = before

    r = await _get(access_token, f"{STRAVA_API_BASE}/athlete/activities", params)
    r.raise_for_status()
    return r.json()


async def get_activity_streams(access_token: str, activity_id: int) -> dict[str, list]:
    r = await _get(
        access_token,
        f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
        {"keys": STREAM_KEYS, "key_by_type": "true"},
    )
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return {k: v["data"] for k, v in r.json().items()}


async def get_activity_laps(access_token: str, activity_id: int) -> list[dict]:
    r = await _get(access_token, f"{STRAVA_API_BASE}/activities/{activity_id}/laps")
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json()


def strava_hash(strava_id: int) -> str:
    return hashlib.sha256(f"strava-{strava_id}".encode()).hexdigest()


def _naive_utc(dt_str: str | None) -> datetime | None:
    """Parsea ISO 8601 UTC y devuelve datetime naive (sin tzinfo) para compatibilidad con TIMESTAMP WITHOUT TIME ZONE."""
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)


def build_bbox_wkt(latlng_stream: list) -> str | None:
    """Construye un WKT POLYGON bounding box a partir de una lista de [lat, lon]."""
    if not latlng_stream:
        return None
    lats = [p[0] for p in latlng_stream]
    lons = [p[1] for p in latlng_stream]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    return (
        f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
        f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
    )


def parse_strava_records(started_at: "datetime | None", streams: dict) -> list[dict]:
    """Extrae la serie temporal de un dict de streams Strava."""
    time_stream: list = streams.get("time", [])
    latlng_stream: list = streams.get("latlng", [])
    dist_stream: list = streams.get("distance", [])
    spd_stream: list = streams.get("velocity_smooth", [])
    alt_stream: list = streams.get("altitude", [])
    hr_stream: list = streams.get("heartrate", [])
    cad_stream: list = streams.get("cadence", [])
    pwr_stream: list = streams.get("watts", [])
    temp_stream: list = streams.get("temp", [])

    records: list[dict] = []
    for i, t in enumerate(time_stream):
        point = latlng_stream[i] if i < len(latlng_stream) else None
        lat = point[0] if point is not None else None
        lon = point[1] if point is not None else None
        ts = started_at + timedelta(seconds=t) if started_at is not None else None
        records.append({
            "ts": ts,
            "lat": lat,
            "lon": lon,
            "altitude_m": alt_stream[i] if i < len(alt_stream) else None,
            "distance_m": dist_stream[i] if i < len(dist_stream) else None,
            "speed_mps": spd_stream[i] if i < len(spd_stream) else None,
            "heart_rate": int(hr_stream[i]) if i < len(hr_stream) else None,
            "cadence": int(cad_stream[i]) if i < len(cad_stream) else None,
            "power": int(pwr_stream[i]) if i < len(pwr_stream) else None,
            "temperature": int(temp_stream[i]) if i < len(temp_stream) else None,
        })
    return records


def parse_strava_laps(laps_data: list[dict]) -> list[dict]:
    """Convierte la lista de laps de Strava al formato interno."""
    laps: list[dict] = []
    for i, lap in enumerate(laps_data):
        st = _naive_utc(lap.get("start_date"))
        laps.append({
            "lap_index": i,
            "start_time": st,
            "duration_s": lap.get("elapsed_time"),
            "distance_m": lap.get("distance"),
            "avg_speed_mps": lap.get("average_speed"),
            "avg_hr": lap.get("average_heartrate"),
            "ascent_m": lap.get("total_elevation_gain"),
        })
    return laps


def strava_to_parsed(activity: dict, streams: dict, laps_data: list[dict]) -> ParsedFit:
    strava_id = activity["id"]
    started_at = _naive_utc(activity.get("start_date"))

    # ── punto de inicio ──────────────────────────────────────────────────────
    start_latlng = activity.get("start_latlng") or []
    start_point_wkt = None
    if len(start_latlng) == 2:
        lat, lon = start_latlng
        start_point_wkt = f"POINT({lon} {lat})"

    # ── bounding box y records desde streams ────────────────────────────────
    latlng_stream: list = streams.get("latlng", [])
    bbox_wkt = build_bbox_wkt(latlng_stream)
    records = parse_strava_records(started_at, streams)
    laps = parse_strava_laps(laps_data)

    return ParsedFit(
        file_hash=strava_hash(strava_id),
        file_name=f"strava_{strava_id}.json",
        started_at=started_at,
        name=activity.get("name") or None,
        sport=activity.get("sport_type") or activity.get("type"),
        duration_s=activity.get("elapsed_time"),
        moving_time_s=activity.get("moving_time"),
        distance_m=activity.get("distance"),
        ascent_m=activity.get("total_elevation_gain"),
        descent_m=None,
        avg_speed_mps=activity.get("average_speed"),
        max_speed_mps=activity.get("max_speed"),
        avg_hr=int(activity["average_heartrate"]) if activity.get("average_heartrate") else None,
        max_hr=int(activity["max_heartrate"]) if activity.get("max_heartrate") else None,
        avg_cadence=int(activity["average_cadence"]) if activity.get("average_cadence") else None,
        avg_power=int(activity["average_watts"]) if activity.get("average_watts") else None,
        calories=activity.get("calories"),
        start_point_wkt=start_point_wkt,
        bbox_wkt=bbox_wkt,
        records=records,
        laps=laps,
    )
