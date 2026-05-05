"""Tests del endpoint POST /activities/upload y del parser FIT."""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from fitapp.services.fit_parser import parse_fit
from tests.conftest import login_user, register_user

# Fichero FIT real montado en el contenedor
_SAMPLE_FIT = Path("/activities/240714102315.fit")


# ── parse_fit (unit) ─────────────────────────────────────────────────────────
def test_parse_fit_returns_hash_and_name() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert len(parsed.file_hash) == 64
    assert parsed.file_name == "240714102315.fit"


def test_parse_fit_session_data() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert parsed.started_at is not None
    assert parsed.sport == "cycling"
    assert parsed.duration_s is not None and parsed.duration_s > 0
    assert parsed.distance_m is not None and parsed.distance_m > 0
    assert parsed.ascent_m is not None and parsed.ascent_m > 0


def test_parse_fit_records() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert len(parsed.records) > 100
    first = parsed.records[0]
    assert first["ts"] is not None
    # Al menos algunos records tienen GPS
    gps = [r for r in parsed.records if r["lat"] is not None]
    assert len(gps) > 100


def test_parse_fit_laps() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert len(parsed.laps) >= 1
    assert parsed.laps[0]["start_time"] is not None
    assert parsed.laps[0]["lap_index"] == 0


def test_parse_fit_bbox_wkt() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert parsed.bbox_wkt is not None
    assert parsed.bbox_wkt.startswith("POLYGON(")


def test_parse_fit_start_point_wkt() -> None:
    parsed = parse_fit(_SAMPLE_FIT)
    assert parsed.start_point_wkt is not None
    assert parsed.start_point_wkt.startswith("POINT(")


def test_parse_fit_invalid_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.fit"
    bad.write_bytes(b"esto no es un fichero FIT valido")
    with pytest.raises(Exception):
        parse_fit(bad)


# ── POST /activities/upload ──────────────────────────────────────────────────
async def test_upload_success(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert res.status_code == 201
    body = res.json()
    assert body["file_name"] == "240714102315.fit"
    assert body["sport"] == "cycling"
    assert body["distance_m"] is not None and body["distance_m"] > 0
    assert body["started_at"] is not None
    assert "id" in body


async def test_upload_duplicate_returns_409(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    with _SAMPLE_FIT.open("rb") as f:
        await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers=headers,
        )

    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers=headers,
        )

    assert res.status_code == 409
    assert "ACTIVITY_ALREADY_EXISTS" in res.text


async def test_upload_requires_auth(client: AsyncClient) -> None:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
        )
    assert res.status_code == 401


async def test_upload_invalid_file_returns_400(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.post(
        "/activities/upload",
        files={"file": ("bad.fit", b"no es un fit", "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "INVALID_FIT_FILE" in res.text


async def test_upload_same_file_different_users_both_succeed(client: AsyncClient) -> None:
    await register_user(client, "user1@example.com")
    await register_user(client, "user2@example.com")
    token1 = await login_user(client, "user1@example.com")
    token2 = await login_user(client, "user2@example.com")

    with _SAMPLE_FIT.open("rb") as f:
        res1 = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token1}"},
        )
    with _SAMPLE_FIT.open("rb") as f:
        res2 = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token2}"},
        )

    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]
