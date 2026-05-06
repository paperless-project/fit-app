"""Tests de los endpoints /stats/*."""
from __future__ import annotations

from pathlib import Path

import pytest
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


# ── /stats/summary ────────────────────────────────────────────────────────────

async def test_stats_summary_empty(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["total_activities"] == 0
    assert body["total_km"] == 0.0
    assert body["total_hours"] == 0.0
    assert body["total_ascent_m"] == 0.0


async def test_stats_summary_with_data(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["total_activities"] == 1
    assert body["total_km"] == pytest.approx(activity["distance_m"] / 1000, rel=1e-3)
    assert body["total_hours"] > 0
    assert body["total_ascent_m"] >= 0


async def test_stats_summary_isolation(client: AsyncClient) -> None:
    await register_user(client, "u1@example.com")
    await register_user(client, "u2@example.com")
    t1 = await login_user(client, "u1@example.com")
    t2 = await login_user(client, "u2@example.com")
    await _upload(client, t1)

    res = await client.get("/stats/summary", headers={"Authorization": f"Bearer {t2}"})
    assert res.json()["total_activities"] == 0


async def test_stats_summary_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/stats/summary")
    assert res.status_code == 401


# ── /stats/calendar ───────────────────────────────────────────────────────────

async def test_stats_calendar_empty(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/stats/calendar?year=2024", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["year"] == 2024
    assert body["days"] == {}


async def test_stats_calendar_with_data(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    started_at = activity["started_at"]
    year = int(started_at[:4])
    date_key = started_at[:10]

    res = await client.get(
        f"/stats/calendar?year={year}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert date_key in body["days"]
    day = body["days"][date_key]
    assert day["count"] == 1
    assert day["km"] > 0


async def test_stats_calendar_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/stats/calendar?year=2024")
    assert res.status_code == 401


async def test_stats_calendar_missing_year(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    res = await client.get("/stats/calendar", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422


# ── /stats/timeline ───────────────────────────────────────────────────────────

async def test_stats_timeline_empty(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/stats/timeline", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


async def test_stats_timeline_with_data(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get("/stats/timeline", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    e = entries[0]
    assert e["period"] == activity["started_at"][:7]
    assert e["count"] == 1
    assert e["km"] > 0
    assert e["hours"] > 0
    assert e["ascent_m"] >= 0


async def test_stats_timeline_year_bucket(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get(
        "/stats/timeline?bucket=year",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    assert entries[0]["period"] == activity["started_at"][:4]


async def test_stats_timeline_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/stats/timeline")
    assert res.status_code == 401
