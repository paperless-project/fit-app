"""Tests de PATCH /users/me/password."""
from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import login_user, register_user


async def test_change_password_ok(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        "/users/me/password",
        json={"current_password": "pass1234", "new_password": "nuevapass99"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["detail"] == "PASSWORD_CHANGED"

    # Verificar que el login con la nueva contraseña funciona
    new_token = await login_user(client, password="nuevapass99")
    assert new_token


async def test_change_password_wrong_current(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        "/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "nuevapass99"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "INVALID_CURRENT_PASSWORD"


async def test_change_password_new_too_short(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.patch(
        "/users/me/password",
        json={"current_password": "pass1234", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


async def test_change_password_requires_auth(client: AsyncClient) -> None:
    res = await client.patch(
        "/users/me/password",
        json={"current_password": "pass1234", "new_password": "nuevapass99"},
    )
    assert res.status_code == 401
