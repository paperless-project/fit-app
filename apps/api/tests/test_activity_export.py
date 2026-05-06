"""Tests de exportación: GPX y CSV."""
from __future__ import annotations

import uuid
from pathlib import Path

from httpx import AsyncClient

from tests.conftest import login_user, register_user

_SAMPLE_FIT = Path("/activities/240714102315.fit")


async def _upload(client: AsyncClient, token: str) -> dict:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    return res.json()


# ── GPX ───────────────────────────────────────────────────────────────────────

async def test_export_gpx_returns_xml(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get(
        f"/activities/{activity['id']}/export/gpx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "gpx" in res.headers["content-type"]
    assert res.headers["content-disposition"].endswith(".gpx")
    body = res.text
    assert "<gpx" in body
    assert "<trkpt" in body
    assert "<time>" in body


async def test_export_gpx_contains_elevation(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get(
        f"/activities/{activity['id']}/export/gpx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "<ele>" in res.text


async def test_export_gpx_not_found(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get(
        f"/activities/{uuid.uuid4()}/export/gpx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


async def test_export_gpx_other_user_returns_404(client: AsyncClient) -> None:
    await register_user(client, "u1@example.com")
    await register_user(client, "u2@example.com")
    t1 = await login_user(client, "u1@example.com")
    t2 = await login_user(client, "u2@example.com")
    activity = await _upload(client, t1)

    res = await client.get(
        f"/activities/{activity['id']}/export/gpx",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert res.status_code == 404


async def test_export_gpx_requires_auth(client: AsyncClient) -> None:
    res = await client.get(f"/activities/{uuid.uuid4()}/export/gpx")
    assert res.status_code == 401


# ── CSV ───────────────────────────────────────────────────────────────────────

async def test_export_csv_returns_csv(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    await _upload(client, token)

    res = await client.get(
        "/activities/export/csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("fecha,nombre,deporte")
    assert len(lines) == 2  # header + 1 actividad


async def test_export_csv_empty(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get(
        "/activities/export/csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    lines = res.text.strip().splitlines()
    assert len(lines) == 1  # solo header


async def test_export_csv_respects_sport_filter(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    await _upload(client, token)

    res = await client.get(
        "/activities/export/csv?sport=running",
        headers={"Authorization": f"Bearer {token}"},
    )
    lines = res.text.strip().splitlines()
    assert len(lines) == 1  # solo header


async def test_export_csv_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/activities/export/csv")
    assert res.status_code == 401
