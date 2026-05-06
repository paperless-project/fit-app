"""Tests del endpoint /activities/."""
from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from tests.conftest import login_user, register_user

_SAMPLE_FIT = Path("/activities/240714102315.fit")


async def test_list_activities_returns_empty_for_new_user(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/activities/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


async def test_list_activities_returns_uploaded(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    with _SAMPLE_FIT.open("rb") as f:
        await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers=headers,
        )

    res = await client.get("/activities/", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["file_name"] == "240714102315.fit"


async def test_list_activities_only_own(client: AsyncClient) -> None:
    await register_user(client, "a@example.com")
    await register_user(client, "b@example.com")
    token_a = await login_user(client, "a@example.com")
    token_b = await login_user(client, "b@example.com")

    with _SAMPLE_FIT.open("rb") as f:
        await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token_a}"},
        )

    res = await client.get("/activities/", headers={"Authorization": f"Bearer {token_b}"})
    assert res.status_code == 200
    assert res.json()["total"] == 0


async def test_list_activities_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/activities/")
    assert res.status_code == 401


async def test_list_activities_invalid_token(client: AsyncClient) -> None:
    res = await client.get("/activities/", headers={"Authorization": "Bearer token.invalido"})
    assert res.status_code == 401
