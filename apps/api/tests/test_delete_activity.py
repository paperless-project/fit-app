"""Tests de DELETE /activities/{id}."""
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


async def test_delete_activity_owner(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.delete(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


async def test_delete_activity_other_user_returns_403(client: AsyncClient) -> None:
    await register_user(client, "u1@example.com")
    await register_user(client, "u2@example.com")
    t1 = await login_user(client, "u1@example.com")
    t2 = await login_user(client, "u2@example.com")
    activity = await _upload(client, t1)

    res = await client.delete(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert res.status_code == 403


async def test_delete_activity_not_found(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.delete(
        f"/activities/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


async def test_delete_activity_requires_auth(client: AsyncClient) -> None:
    res = await client.delete(f"/activities/{uuid.uuid4()}")
    assert res.status_code == 401


async def test_delete_all_activities(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _upload(client, token)

    res = await client.get("/activities/", headers=headers)
    assert res.json()["total"] >= 1

    res = await client.delete("/activities", headers=headers)
    assert res.status_code == 204

    res = await client.get("/activities/", headers=headers)
    assert res.json()["total"] == 0


async def test_delete_all_activities_requires_auth(client: AsyncClient) -> None:
    res = await client.delete("/activities")
    assert res.status_code == 401


async def test_delete_all_activities_only_own(client: AsyncClient) -> None:
    """Borrar todas las actividades de un usuario no afecta a otros usuarios."""
    await register_user(client, "owner@example.com")
    await register_user(client, "other@example.com")
    t_owner = await login_user(client, "owner@example.com")
    t_other = await login_user(client, "other@example.com")

    activity_other = await _upload(client, t_other)

    await client.delete("/activities", headers={"Authorization": f"Bearer {t_owner}"})

    res = await client.get(
        f"/activities/{activity_other['id']}",
        headers={"Authorization": f"Bearer {t_other}"},
    )
    assert res.status_code == 200
