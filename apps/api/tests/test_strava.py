"""Tests de la integración con Strava: servicio y endpoints."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from fitapp.services.strava_service import is_token_expired, strava_hash, strava_to_parsed
from tests.conftest import login_user, register_user


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_activity(strava_id: int = 111) -> dict:
    return {
        "id": strava_id,
        "name": "Ruta mañana",
        "sport_type": "Ride",
        "start_date": "2024-03-15T08:00:00Z",
        "elapsed_time": 3600,
        "moving_time": 3500,
        "distance": 40000.0,
        "total_elevation_gain": 500.0,
        "average_speed": 11.1,
        "max_speed": 18.0,
        "average_heartrate": 145.0,
        "max_heartrate": 170.0,
        "average_cadence": 88.0,
        "average_watts": 220.0,
        "calories": 900,
        "start_latlng": [43.3, -1.98],
    }


def _fake_streams() -> dict:
    return {
        "time": [0, 1, 2],
        "latlng": [[43.3, -1.98], [43.301, -1.981], [43.302, -1.982]],
        "altitude": [50.0, 51.0, 52.0],
        "heartrate": [140, 142, 144],
        "cadence": [85, 86, 87],
        "watts": [200, 210, 220],
        "temp": [18, 18, 19],
        "distance": [0.0, 5.0, 10.0],
        "velocity_smooth": [10.0, 11.0, 11.5],
    }


async def _auth_headers(client: AsyncClient) -> dict:
    await register_user(client)
    token = await login_user(client)
    return {"Authorization": f"Bearer {token}"}


# ── Tests de strava_service (puras, sin BD) ────────────────────────────────────

def test_strava_hash_deterministic() -> None:
    assert strava_hash(12345) == strava_hash(12345)


def test_strava_hash_no_collision() -> None:
    assert strava_hash(1) != strava_hash(2)


def test_strava_hash_prefixed() -> None:
    # El hash debe diferir del sha256 del entero sin prefijo
    import hashlib
    raw = hashlib.sha256(b"12345").hexdigest()
    assert strava_hash(12345) != raw


def test_is_token_expired_past() -> None:
    assert is_token_expired(int(time.time()) - 10) is True


def test_is_token_expired_future() -> None:
    assert is_token_expired(int(time.time()) + 3600) is False


def test_is_token_expired_within_margin() -> None:
    # Expira en 30 s (< 60 s de margen) → debe considerarse expirado
    assert is_token_expired(int(time.time()) + 30) is True


def test_strava_to_parsed_basic() -> None:
    parsed = strava_to_parsed(_fake_activity(), {}, [])
    assert parsed.sport == "Ride"
    assert parsed.distance_m == 40000.0
    assert parsed.avg_hr == 145
    assert parsed.avg_power == 220
    assert parsed.file_name == "strava_111.json"
    assert parsed.file_hash == strava_hash(111)


def test_strava_to_parsed_start_point() -> None:
    parsed = strava_to_parsed(_fake_activity(), {}, [])
    # start_latlng [lat, lon] → WKT POINT(lon lat)
    assert parsed.start_point_wkt == "POINT(-1.98 43.3)"


def test_strava_to_parsed_no_gps() -> None:
    act = _fake_activity()
    act["start_latlng"] = []
    parsed = strava_to_parsed(act, {}, [])
    assert parsed.start_point_wkt is None
    assert parsed.bbox_wkt is None
    assert parsed.records == []


def test_strava_to_parsed_with_streams() -> None:
    parsed = strava_to_parsed(_fake_activity(), _fake_streams(), [])
    assert len(parsed.records) == 3
    r0 = parsed.records[0]
    assert r0["lat"] == pytest.approx(43.3)
    assert r0["lon"] == pytest.approx(-1.98)
    assert r0["heart_rate"] == 140
    assert r0["power"] == 200
    assert r0["cadence"] == 85
    assert r0["temperature"] == 18


def test_strava_to_parsed_timestamps() -> None:
    parsed = strava_to_parsed(_fake_activity(), _fake_streams(), [])
    t0 = parsed.records[0]["ts"]
    t1 = parsed.records[1]["ts"]
    assert t0 is not None
    assert t0.tzinfo is None  # debe ser naive para TIMESTAMP WITHOUT TIME ZONE
    assert (t1 - t0).total_seconds() == pytest.approx(1.0)


def test_strava_to_parsed_bbox() -> None:
    parsed = strava_to_parsed(_fake_activity(), _fake_streams(), [])
    assert parsed.bbox_wkt is not None
    assert parsed.bbox_wkt.startswith("POLYGON(")


def test_strava_to_parsed_laps() -> None:
    laps = [
        {"start_date": "2024-03-15T08:00:00Z", "elapsed_time": 1800,
         "distance": 20000.0, "average_speed": 11.0, "average_heartrate": 140,
         "total_elevation_gain": 200},
    ]
    parsed = strava_to_parsed(_fake_activity(), {}, laps)
    assert len(parsed.laps) == 1
    assert parsed.laps[0]["lap_index"] == 0
    assert parsed.laps[0]["duration_s"] == 1800


# ── Tests de endpoints ─────────────────────────────────────────────────────────

async def test_strava_status_not_connected(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    res = await client.get("/strava/status", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"connected": False}


async def test_strava_status_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/strava/status")
    assert res.status_code == 401


async def test_strava_status_connected(client: AsyncClient) -> None:
    from fitapp.models.user import StravaToken
    from fitapp.db import get_session
    from tests.conftest import _SessionFactory

    headers = await _auth_headers(client)

    # Obtener user_id del /users/me
    me = await client.get("/users/me", headers=headers)
    user_id = me.json()["id"]

    # Insertar token directamente en BD de test
    async with _SessionFactory() as db:
        db.add(StravaToken(
            user_id=user_id,
            access_token="tok",
            refresh_token="ref",
            expires_at=int(time.time()) + 3600,
            athlete_id=99999,
        ))
        await db.commit()

    res = await client.get("/strava/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert data["athlete_id"] == 99999


async def test_strava_disconnect_no_token(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    res = await client.delete("/strava/disconnect", headers=headers)
    assert res.status_code == 204


async def test_strava_disconnect_removes_token(client: AsyncClient) -> None:
    from fitapp.models.user import StravaToken
    from tests.conftest import _SessionFactory
    from sqlalchemy import select

    headers = await _auth_headers(client)
    me = await client.get("/users/me", headers=headers)
    user_id = me.json()["id"]

    async with _SessionFactory() as db:
        db.add(StravaToken(
            user_id=user_id,
            access_token="tok",
            refresh_token="ref",
            expires_at=int(time.time()) + 3600,
        ))
        await db.commit()

    res = await client.delete("/strava/disconnect", headers=headers)
    assert res.status_code == 204

    async with _SessionFactory() as db:
        from fitapp.models.user import StravaToken as ST
        import uuid
        result = await db.execute(select(ST).where(ST.user_id == uuid.UUID(user_id)))
        assert result.scalar_one_or_none() is None


async def test_strava_authorize_returns_url(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    res = await client.get("/strava/authorize", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "authorization_url" in data
    assert "strava.com/oauth/authorize" in data["authorization_url"]


async def test_strava_callback_error_param(client: AsyncClient) -> None:
    res = await client.get(
        "/strava/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert "strava_error=access_denied" in res.headers["location"]


async def test_strava_callback_missing_code(client: AsyncClient) -> None:
    res = await client.get("/strava/callback", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert "strava_error" in res.headers["location"]


async def test_strava_callback_invalid_state(client: AsyncClient) -> None:
    res = await client.get(
        "/strava/callback",
        params={"code": "abc", "state": "bad_state"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert "strava_error=invalid_state" in res.headers["location"]


async def test_strava_callback_success(client: AsyncClient) -> None:
    import jwt as pyjwt
    from fitapp.config import settings

    headers = await _auth_headers(client)
    me = await client.get("/users/me", headers=headers)
    user_id = me.json()["id"]

    # Generar un state válido con el user_id
    state = pyjwt.encode(
        {"sub": user_id, "aud": "strava-oauth"},
        settings.jwt_secret,
        algorithm="HS256",
    )

    fake_token_data = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": int(time.time()) + 3600,
        "athlete": {"id": 77777},
    }
    with patch(
        "fitapp.routers.strava.ss.exchange_code",
        new_callable=AsyncMock,
        return_value=fake_token_data,
    ):
        res = await client.get(
            "/strava/callback",
            params={"code": "authcode123", "state": state},
            follow_redirects=False,
        )

    assert res.status_code in (302, 307)
    assert "strava_connected=1" in res.headers["location"]


async def test_strava_callback_exchange_failure(client: AsyncClient) -> None:
    import jwt as pyjwt
    from fitapp.config import settings

    headers = await _auth_headers(client)
    me = await client.get("/users/me", headers=headers)
    user_id = me.json()["id"]

    state = pyjwt.encode(
        {"sub": user_id, "aud": "strava-oauth"},
        settings.jwt_secret,
        algorithm="HS256",
    )

    with patch(
        "fitapp.routers.strava.ss.exchange_code",
        new_callable=AsyncMock,
        side_effect=Exception("network error"),
    ):
        res = await client.get(
            "/strava/callback",
            params={"code": "bad_code", "state": state},
            follow_redirects=False,
        )

    assert res.status_code in (302, 307)
    assert "strava_error=exchange_failed" in res.headers["location"]


async def test_strava_import_no_token(client: AsyncClient) -> None:
    headers = await _auth_headers(client)
    res = await client.post("/strava/import", headers=headers)
    assert res.status_code == 401


async def test_strava_import_enqueued(client: AsyncClient) -> None:
    from fitapp.models.user import StravaToken
    from tests.conftest import _SessionFactory

    headers = await _auth_headers(client)
    me = await client.get("/users/me", headers=headers)
    user_id = me.json()["id"]

    async with _SessionFactory() as db:
        db.add(StravaToken(
            user_id=user_id,
            access_token="tok",
            refresh_token="ref",
            expires_at=int(time.time()) + 3600,
        ))
        await db.commit()

    with patch("fitapp.routers.strava._import_bg", new_callable=AsyncMock):
        res = await client.post("/strava/import", headers=headers)

    assert res.status_code == 200
    assert res.json()["status"] == "import_started"


async def test_strava_authorize_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/strava/authorize")
    assert res.status_code == 401
