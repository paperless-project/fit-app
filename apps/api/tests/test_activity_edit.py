"""Tests de PATCH /activities/{id}."""
from __future__ import annotations

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


async def test_patch_name(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Vuelta por la montaña"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Vuelta por la montaña"


async def test_patch_sport(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.patch(
        f"/activities/{activity['id']}",
        json={"sport": "gravel"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["sport"] == "gravel"


async def test_patch_notes(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.patch(
        f"/activities/{activity['id']}",
        json={"notes": "Salida con viento fuerte, piernas cargadas."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["notes"] == "Salida con viento fuerte, piernas cargadas."


async def test_patch_partial_does_not_overwrite_other_fields(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)
    original_sport = activity["sport"]

    await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Nuevo nombre"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["sport"] == original_sport


async def test_patch_not_found(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    import uuid
    res = await client.patch(
        f"/activities/{uuid.uuid4()}",
        json={"name": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


async def test_patch_other_user_returns_404(client: AsyncClient) -> None:
    await register_user(client, "u1@example.com")
    await register_user(client, "u2@example.com")
    t1 = await login_user(client, "u1@example.com")
    t2 = await login_user(client, "u2@example.com")
    activity = await _upload(client, t1)

    res = await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Intento de hackeo"},
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert res.status_code == 404


async def test_patch_requires_auth(client: AsyncClient) -> None:
    import uuid
    res = await client.patch(f"/activities/{uuid.uuid4()}", json={"name": "X"})
    assert res.status_code == 401
