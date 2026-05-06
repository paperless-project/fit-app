"""Tests de DELETE /users/me."""
from __future__ import annotations

import json
from pathlib import Path

from httpx import AsyncClient

from tests.conftest import login_user, register_user

_SAMPLE_FIT = Path("/activities/240714102315.fit")

_JSON_HEADERS = {"Content-Type": "application/json"}


async def _upload(client: AsyncClient, token: str) -> dict:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    return res.json()


async def _delete_account(client: AsyncClient, token: str, confirm: bool):
    return await client.request(
        "DELETE",
        "/users/me",
        content=json.dumps({"confirm": confirm}),
        headers={"Authorization": f"Bearer {token}", **_JSON_HEADERS},
    )


async def test_delete_account_ok(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await _delete_account(client, token, confirm=True)
    assert res.status_code == 204

    # El token ya no es válido porque el usuario no existe
    res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_delete_account_cascades_activities(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await _delete_account(client, token, confirm=True)
    assert res.status_code == 204

    # Registrar nuevo usuario y verificar que la actividad ya no existe
    await register_user(client, "other@example.com")
    other_token = await login_user(client, "other@example.com")
    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res.status_code == 404


async def test_delete_account_requires_confirmation(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await _delete_account(client, token, confirm=False)
    assert res.status_code == 400
    assert res.json()["detail"] == "CONFIRMATION_REQUIRED"


async def test_delete_account_requires_auth(client: AsyncClient) -> None:
    res = await client.request(
        "DELETE",
        "/users/me",
        content=json.dumps({"confirm": True}),
        headers=_JSON_HEADERS,
    )
    assert res.status_code == 401
