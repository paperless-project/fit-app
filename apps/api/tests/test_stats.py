"""Tests del endpoint /stats/summary."""
from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import login_user, register_user


async def test_stats_summary_returns_zeros(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"total_km": 0, "total_hours": 0, "total_activities": 0}


async def test_stats_summary_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/stats/summary")
    assert res.status_code == 401


async def test_stats_summary_invalid_token(client: AsyncClient) -> None:
    res = await client.get("/stats/summary", headers={"Authorization": "Bearer token.invalido"})
    assert res.status_code == 401
