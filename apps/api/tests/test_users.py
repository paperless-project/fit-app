"""Tests de /users/me (PATCH) y rutas de administracion de usuarios."""
from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import login_user, register_user


# ── PATCH /users/me ──────────────────────────────────────────────────────────
async def test_patch_me_updates_email(client: AsyncClient) -> None:
    await register_user(client, "original@example.com")
    token = await login_user(client, "original@example.com")

    res = await client.patch(
        "/users/me",
        json={"email": "updated@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "updated@example.com"


async def test_patch_me_updates_password(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        "/users/me",
        json={"password": "newpassword1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # El nuevo password debe funcionar para hacer login
    new_token = await login_user(client, password="newpassword1")
    assert new_token


async def test_patch_me_requires_auth(client: AsyncClient) -> None:
    res = await client.patch("/users/me", json={"email": "x@x.com"})
    assert res.status_code == 401


async def test_patch_me_duplicate_email(client: AsyncClient) -> None:
    await register_user(client, "a@example.com")
    await register_user(client, "b@example.com")
    token = await login_user(client, "a@example.com")

    res = await client.patch(
        "/users/me",
        json={"email": "b@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "UPDATE_USER_EMAIL_ALREADY_EXISTS" in res.text


async def test_patch_me_short_password(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        "/users/me",
        json={"password": "abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "UPDATE_USER_INVALID_PASSWORD" in res.text


# ── Rutas de admin requieren superuser ───────────────────────────────────────
async def test_get_user_by_id_requires_superuser(client: AsyncClient) -> None:
    user = await register_user(client)
    token = await login_user(client)

    res = await client.get(
        f"/users/{user['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


async def test_patch_user_by_id_requires_superuser(client: AsyncClient) -> None:
    user = await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        f"/users/{user['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


async def test_delete_user_requires_superuser(client: AsyncClient) -> None:
    user = await register_user(client)
    token = await login_user(client)

    res = await client.delete(
        f"/users/{user['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403
