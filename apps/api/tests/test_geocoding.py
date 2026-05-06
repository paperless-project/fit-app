"""Tests del servicio de geocodificacion."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import fitapp.services.geocoding as geo


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_records(n: int = 100) -> list[dict]:
    """Records con GPS simples para usar en tests."""
    return [{"lat": 42.8 + i * 0.001, "lon": -8.5 + i * 0.001} for i in range(n)]


def _nominatim_response(cls: str, type_: str, name: str, address: dict) -> dict:
    return {"class": cls, "type": type_, "name": name, "address": address}


def _village_response(village: str) -> dict:
    return _nominatim_response("place", "village", village, {"village": village})


def _poi_response(name: str, cls: str = "amenity") -> dict:
    return _nominatim_response(cls, "place_of_worship", name, {"village": "Aldea"})


# ── Tests de helpers internos ────────────────────────────────────────────────

def test_locality_hamlet_first():
    address = {"hamlet": "O Milladoiro", "town": "Ames"}
    assert geo._locality(address) == "O Milladoiro"


def test_locality_fallback_to_city():
    address = {"city": "Santiago de Compostela"}
    assert geo._locality(address) == "Santiago de Compostela"


def test_locality_empty():
    assert geo._locality({}) is None


def test_poi_name_notable_class():
    result = {"class": "tourism", "name": "Mirador das Illas Cies"}
    assert geo._poi_name(result) == "Mirador das Illas Cies"


def test_poi_name_highway_not_notable():
    result = {"class": "highway", "name": "Rúa Mayor"}
    assert geo._poi_name(result) is None


def test_poi_name_no_name():
    result = {"class": "amenity", "name": ""}
    assert geo._poi_name(result) is None


# ── Tests de generate_activity_name ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_name_no_gps_returns_none():
    records = [{"lat": None, "lon": None}] * 10
    result = await geo.generate_activity_name(records)
    assert result is None


@pytest.mark.asyncio
async def test_generate_name_only_locality():
    records = _make_records(100)
    responses = [_village_response("O Milladoiro")] + [None, None, None]

    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, side_effect=responses):
        name = await geo.generate_activity_name(records)

    assert name == "Desde O Milladoiro"


@pytest.mark.asyncio
async def test_generate_name_one_poi():
    records = _make_records(100)
    responses = [
        _village_response("Padrón"),
        _poi_response("Santuario de la Esclavitud"),
        None,
        None,
    ]

    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, side_effect=responses):
        name = await geo.generate_activity_name(records)

    assert name == "Santuario de la Esclavitud desde Padrón"


@pytest.mark.asyncio
async def test_generate_name_two_pois():
    records = _make_records(100)
    responses = [
        _village_response("O Milladoiro"),
        _poi_response("Santuario de la Esclavitud"),
        _poi_response("Monumento a Cela"),
        None,
    ]

    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, side_effect=responses):
        name = await geo.generate_activity_name(records)

    assert name == "Santuario de la Esclavitud y Monumento a Cela desde O Milladoiro"


@pytest.mark.asyncio
async def test_generate_name_three_pois():
    records = _make_records(100)
    responses = [
        _village_response("O Milladoiro"),
        _poi_response("Santuario de la Esclavitud"),
        _poi_response("Monumento a Cela"),
        _poi_response("Igrexa de Iria Flavia", cls="historic"),
    ]

    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, side_effect=responses):
        name = await geo.generate_activity_name(records)

    assert name == (
        "Santuario de la Esclavitud, Monumento a Cela y Igrexa de Iria Flavia desde O Milladoiro"
    )


@pytest.mark.asyncio
async def test_generate_name_deduplicates_pois():
    """Si dos puntos de muestreo devuelven el mismo POI, aparece solo una vez."""
    records = _make_records(100)
    responses = [
        _village_response("Padrón"),
        _poi_response("Santuario de la Esclavitud"),
        _poi_response("Santuario de la Esclavitud"),  # duplicado
        None,
    ]

    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, side_effect=responses):
        name = await geo.generate_activity_name(records)

    assert name == "Santuario de la Esclavitud desde Padrón"


@pytest.mark.asyncio
async def test_generate_name_all_geocoding_fails():
    records = _make_records(100)
    with patch("fitapp.services.geocoding._reverse", new_callable=AsyncMock, return_value=None):
        name = await geo.generate_activity_name(records)
    assert name is None


@pytest.mark.asyncio
async def test_generate_name_empty_records():
    result = await geo.generate_activity_name([])
    assert result is None
