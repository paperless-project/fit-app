"""Parseo de ficheros FIT con fitparse."""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_SEMICIRCLE = 180.0 / (2**31)


def _deg(semicircles: int | None) -> float | None:
    return semicircles * _SEMICIRCLE if semicircles is not None else None


def _first(*vals: Any) -> Any:
    """Devuelve el primer valor no-None."""
    for v in vals:
        if v is not None:
            return v
    return None


@dataclass
class ParsedFit:
    file_hash: str
    file_name: str
    started_at: datetime | None = None
    name: str | None = None
    sport: str | None = None
    duration_s: int | None = None
    moving_time_s: int | None = None
    distance_m: float | None = None
    ascent_m: float | None = None
    descent_m: float | None = None
    avg_speed_mps: float | None = None
    max_speed_mps: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_cadence: int | None = None
    avg_power: int | None = None
    calories: int | None = None
    start_point_wkt: str | None = None  # "POINT(lon lat)"
    bbox_wkt: str | None = None         # "POLYGON(...)"
    records: list[dict[str, Any]] = field(default_factory=list)
    laps: list[dict[str, Any]] = field(default_factory=list)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_fit(path: Path) -> ParsedFit:
    """Parsea un fichero FIT y devuelve un ParsedFit listo para persistir."""
    import fitparse

    file_hash = file_sha256(path)
    ff = fitparse.FitFile(str(path))

    # ── session (resumen global) ────────────────────────────────────────────
    sv: dict[str, Any] = {}
    for msg in ff.get_messages("session"):
        sv = {d.name: d.value for d in msg if d.value is not None}

    started_at: datetime | None = sv.get("start_time")
    sport = str(sv.get("sport", "")) or None
    duration_s = int(sv["total_elapsed_time"]) if "total_elapsed_time" in sv else None
    moving_time_s = int(sv["total_moving_time"]) if "total_moving_time" in sv else None

    s_lat = _deg(sv.get("start_position_lat"))
    s_lon = _deg(sv.get("start_position_long"))
    start_point_wkt = f"POINT({s_lon} {s_lat})" if s_lat is not None and s_lon is not None else None

    # ── records (serie temporal) ────────────────────────────────────────────
    records: list[dict[str, Any]] = []
    lats: list[float] = []
    lons: list[float] = []

    for msg in ff.get_messages("record"):
        rv = {d.name: d.value for d in msg if d.value is not None}
        ts: datetime | None = rv.get("timestamp")
        if ts is None:
            continue

        lat = _deg(rv.get("position_lat"))
        lon = _deg(rv.get("position_long"))
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)

        records.append({
            "ts": ts,
            "lat": lat,
            "lon": lon,
            "altitude_m": _first(rv.get("enhanced_altitude"), rv.get("altitude")),
            "distance_m": rv.get("distance"),
            "speed_mps": _first(rv.get("enhanced_speed"), rv.get("speed")),
            "heart_rate": rv.get("heart_rate"),
            "cadence": rv.get("cadence"),
            "power": rv.get("power"),
            "temperature": rv.get("temperature"),
        })

    # bounding box a partir de los puntos GPS
    bbox_wkt: str | None = None
    if lats and lons:
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        bbox_wkt = (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
            f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
        )

    # fallback: started_at desde el primer record si no hay sesión
    if started_at is None and records:
        started_at = records[0]["ts"]

    # ── laps ────────────────────────────────────────────────────────────────
    laps: list[dict[str, Any]] = []
    for i, msg in enumerate(ff.get_messages("lap")):
        lv = {d.name: d.value for d in msg if d.value is not None}
        st: datetime | None = lv.get("start_time")
        if st is None:
            continue
        laps.append({
            "lap_index": i,
            "start_time": st,
            "duration_s": int(lv["total_elapsed_time"]) if "total_elapsed_time" in lv else None,
            "distance_m": lv.get("total_distance"),
            "avg_speed_mps": _first(lv.get("enhanced_avg_speed"), lv.get("avg_speed")),
            "avg_hr": lv.get("avg_heart_rate"),
            "ascent_m": lv.get("total_ascent"),
        })

    return ParsedFit(
        file_hash=file_hash,
        file_name=path.name,
        started_at=started_at,
        sport=sport,
        duration_s=duration_s,
        moving_time_s=moving_time_s,
        distance_m=sv.get("total_distance"),
        ascent_m=sv.get("total_ascent"),
        descent_m=sv.get("total_descent"),
        avg_speed_mps=_first(sv.get("enhanced_avg_speed"), sv.get("avg_speed")),
        max_speed_mps=_first(sv.get("enhanced_max_speed"), sv.get("max_speed")),
        avg_hr=sv.get("avg_heart_rate"),
        max_hr=sv.get("max_heart_rate"),
        avg_cadence=sv.get("avg_cadence"),
        avg_power=sv.get("avg_power"),
        calories=sv.get("total_calories"),
        start_point_wkt=start_point_wkt,
        bbox_wkt=bbox_wkt,
        records=records,
        laps=laps,
    )


def parse_fit_safe(path: Path) -> tuple[ParsedFit, bool]:
    """
    Parsea un fichero FIT. Si falla, intenta repararlo antes de volver a parsear.

    Devuelve (ParsedFit, was_repaired).
    El file_hash siempre corresponde al fichero original para que la deduplicacion
    por (user_id, file_hash) sea coherente independientemente de la reparacion.
    """
    from fitapp.services.fit_repair import FitRepairError, repair

    try:
        return parse_fit(path), False
    except Exception as original_error:
        pass

    # Conservar el hash del original antes de reparar
    original_hash = file_sha256(path)
    original_name = path.name

    try:
        repaired_bytes = repair(path)
    except FitRepairError:
        raise Exception(f"No se pudo parsear ni reparar {path.name}")

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(repaired_bytes)
        tmp_path = Path(tmp.name)

    try:
        parsed = parse_fit(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    parsed.file_hash = original_hash
    parsed.file_name = original_name
    return parsed, True
