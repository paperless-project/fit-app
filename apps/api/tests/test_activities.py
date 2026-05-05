"""Tests del endpoint /activities/."""
from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import login_user, register_user


async def test_list_activities_returns_empty_for_new_user(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/activities/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


async def test_list_activities_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/activities/")
    assert res.status_code == 401


async def test_list_activities_invalid_token(client: AsyncClient) -> None:
    res = await client.get("/activities/", headers={"Authorization": "Bearer token.invalido"})
    assert res.status_code == 401
