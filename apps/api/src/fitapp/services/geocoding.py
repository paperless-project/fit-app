"""Geocodificacion inversa con Nominatim (OpenStreetMap).

Genera nombres de actividad estilo Wikiloc:
  Bucle:         "Santuario de la Esclavitud, Igrexa de Iria Flavia desde O Milladoiro"
  Punto a punto: "De O Milladoiro a Padrón vía Igrexa de Iria Flavia"

Respeta la politica de uso de Nominatim: maximo 1 peticion/segundo,
User-Agent identificado. Cache en memoria por cuadricula ~1 km.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx

_NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
_HEADERS = {"User-Agent": "fit-app/1.0 (personal cycling tracker)"}
_TIMEOUT = 5.0
_MIN_INTERVAL = 1.1  # Nominatim: max 1 req/s

# Cache: (round(lat,2), round(lon,2), zoom) → resultado JSON o None
_cache: dict[tuple[float, float, int], dict[str, Any] | None] = {}
_last_call: float = 0.0

# Clases OSM que indican un lugar notable (no simple via o edificio residencial)
_NOTABLE_CLASSES = frozenset({
    "amenity", "tourism", "historic", "natural", "leisure", "man_made",
    "mountain_pass", "waterway",
})

# Radio en km para considerar el recorrido como bucle
_LOOP_THRESHOLD_KM = 1.5


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine en km entre dos puntos GPS."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


async def _reverse(lat: float, lon: float, zoom: int) -> dict[str, Any] | None:
    """Llamada a Nominatim con cache y rate-limiting."""
    global _last_call

    key = (round(lat, 2), round(lon, 2), zoom)
    if key in _cache:
        return _cache[key]

    loop = asyncio.get_running_loop()
    wait = _MIN_INTERVAL - (loop.time() - _last_call)
    if wait > 0:
        await asyncio.sleep(wait)

    result: dict[str, Any] | None = None
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            r = await client.get(
                _NOMINATIM,
                params={"lat": lat, "lon": lon, "format": "json", "zoom": zoom, "addressdetails": 1},
            )
            if r.status_code == 200:
                result = r.json()
    except Exception:
        pass

    _last_call = asyncio.get_running_loop().time()
    _cache[key] = result
    return result


def _locality(address: dict[str, Any]) -> str | None:
    """Extrae el nombre del nucleo mas especifico de un resultado Nominatim."""
    for key in ("hamlet", "village", "suburb", "quarter", "town", "city_district", "city"):
        if v := address.get(key):
            return v
    return None


def _poi_name(result: dict[str, Any]) -> str | None:
    """Devuelve el nombre si el lugar es un POI notable, si no None."""
    if result.get("class") in _NOTABLE_CLASSES:
        name = (result.get("name") or "").strip()
        if name:
            return name
    return None


def _join_pois(pois: list[str]) -> str:
    if len(pois) == 1:
        return pois[0]
    if len(pois) == 2:
        return f"{pois[0]} y {pois[1]}"
    return f"{', '.join(pois[:-1])} y {pois[-1]}"


async def generate_activity_name(records: list[dict[str, Any]]) -> str | None:
    """
    Genera un nombre descriptivo a partir de los records GPS de la actividad.

    Estrategia:
    - Obtiene la localidad de inicio (zoom 13).
    - Obtiene la localidad de fin (zoom 13); si es diferente al inicio = punto a punto.
    - Muestrea hasta 5 waypoints intermedios (fracciones 0.15, 0.3, 0.5, 0.7, 0.85) a zoom 17
      para identificar POIs notables (amenity, tourism, historic, natural, leisure...).
    - Nombres resultado:
        Bucle:         "POI1, POI2 y POI3 desde StartLocality"
        Punto a punto: "De StartLocality a EndLocality [vía POI1]"
    Devuelve None si no hay datos GPS suficientes o todos los geocodings fallan.
    """
    gps = [r for r in records if r.get("lat") is not None and r.get("lon") is not None]
    if len(gps) < 2:
        return None

    n = len(gps)

    # ── 1. Localidad de inicio ────────────────────────────────────────────────
    start_result = await _reverse(gps[0]["lat"], gps[0]["lon"], zoom=13)
    start_locality = _locality(start_result.get("address", {})) if start_result else None

    # ── 2. Localidad de fin (usando el 95% de la ruta para evitar el inicio) ──
    end_idx = max(1, int(n * 0.95))
    end_result = await _reverse(gps[end_idx]["lat"], gps[end_idx]["lon"], zoom=13)
    end_locality = _locality(end_result.get("address", {})) if end_result else None

    # ── 3. ¿Es bucle? ────────────────────────────────────────────────────────
    dist_km = _haversine_km(
        gps[0]["lat"], gps[0]["lon"],
        gps[-1]["lat"], gps[-1]["lon"],
    )
    is_loop = dist_km <= _LOOP_THRESHOLD_KM or start_locality == end_locality

    # ── 4. POIs intermedios ──────────────────────────────────────────────────
    pois: list[str] = []
    seen: set[str] = set()
    if start_locality:
        seen.add(start_locality.lower())
    if end_locality and not is_loop:
        seen.add(end_locality.lower())

    for frac in (0.15, 0.30, 0.50, 0.70, 0.85):
        if len(pois) >= 3:
            break
        idx = int(n * frac)
        result = await _reverse(gps[idx]["lat"], gps[idx]["lon"], zoom=17)
        if result:
            name = _poi_name(result)
            if name and name.lower() not in seen:
                pois.append(name)
                seen.add(name.lower())

    # ── 5. Construir nombre ───────────────────────────────────────────────────
    if is_loop:
        if pois and start_locality:
            return f"{_join_pois(pois)} desde {start_locality}"
        if pois:
            return _join_pois(pois)
        if start_locality:
            return f"Desde {start_locality}"
        return None
    else:
        # Punto a punto
        if start_locality and end_locality and start_locality != end_locality:
            base = f"De {start_locality} a {end_locality}"
        elif start_locality:
            base = f"Desde {start_locality}"
        elif end_locality:
            base = f"Hasta {end_locality}"
        else:
            base = None

        if pois and base:
            return f"{base} vía {_join_pois(pois[:1])}"
        return base
