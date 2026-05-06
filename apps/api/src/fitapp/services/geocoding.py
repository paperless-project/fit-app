"""Geocodificacion inversa con Nominatim (OpenStreetMap).

Genera nombres de actividad estilo Wikiloc:
  "Santuario de la Esclavitud, Igrexa de Iria Flavia desde O Milladoiro"

Respeta la politica de uso de Nominatim: maximo 1 peticion/segundo,
User-Agent identificado. Cache en memoria por cuadricula ~1 km.
"""
from __future__ import annotations

import asyncio
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
})


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


async def generate_activity_name(records: list[dict[str, Any]]) -> str | None:
    """
    Genera un nombre estilo Wikiloc a partir de los records GPS de la actividad.

    Toma 4 puntos (inicio + 25% + 50% + 75% de la ruta), llama a Nominatim y
    construye: "POI1, POI2 y POI3 desde StartLocality".
    Devuelve None si no hay datos GPS suficientes o si todos los geocodings fallan.
    """
    gps = [r for r in records if r.get("lat") is not None and r.get("lon") is not None]
    if len(gps) < 2:
        return None

    # Localidad de partida a zoom bajo (nivel pueblo/ciudad)
    start_result = await _reverse(gps[0]["lat"], gps[0]["lon"], zoom=13)
    start_locality = _locality(start_result.get("address", {})) if start_result else None

    # Puntos intermedios para buscar POIs notables
    n = len(gps)
    pois: list[str] = []
    seen: set[str] = {start_locality} if start_locality else set()

    for frac in (0.25, 0.5, 0.75):
        pt = gps[int(n * frac)]
        result = await _reverse(pt["lat"], pt["lon"], zoom=17)
        if result:
            name = _poi_name(result)
            if name and name not in seen:
                pois.append(name)
                seen.add(name)

    if not pois and not start_locality:
        return None

    if pois:
        if len(pois) == 1:
            poi_str = pois[0]
        elif len(pois) == 2:
            poi_str = f"{pois[0]} y {pois[1]}"
        else:
            poi_str = f"{', '.join(pois[:-1])} y {pois[-1]}"
        return f"{poi_str} desde {start_locality}" if start_locality else poi_str

    return f"Desde {start_locality}"
