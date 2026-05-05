"""Tests del flujo de verificacion de correo electronico."""
from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import AsyncClient

from tests.conftest import login_user, register_user


async def test_register_sends_verification_email(
    client: AsyncClient, mock_send_email: AsyncMock
) -> None:
    await register_user(client)
    mock_send_email.assert_called_once()
    call_email = mock_send_email.call_args[0][0]
    assert call_email == "user@example.com"


async def test_register_user_is_not_verified(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.json()["is_verified"] is False


async def test_verify_success(client: AsyncClient, mock_send_email: AsyncMock) -> None:
    await register_user(client)
    verify_token = mock_send_email.call_args[0][1]

    res = await client.post("/auth/verify", json={"token": verify_token})
    assert res.status_code == 200
    assert res.json()["is_verified"] is True


async def test_verify_invalid_token(client: AsyncClient) -> None:
    res = await client.post("/auth/verify", json={"token": "token.completamente.invalido"})
    assert res.status_code == 400


async def test_verify_already_verified(client: AsyncClient, mock_send_email: AsyncMock) -> None:
    await register_user(client)
    verify_token = mock_send_email.call_args[0][1]

    await client.post("/auth/verify", json={"token": verify_token})

    # Segundo intento con el mismo token
    res = await client.post("/auth/verify", json={"token": verify_token})
    assert res.status_code == 400


async def test_request_verify_token(client: AsyncClient, mock_send_email: AsyncMock) -> None:
    await register_user(client)
    mock_send_email.reset_mock()

    res = await client.post(
        "/auth/request-verify-token", json={"email": "user@example.com"}
    )
    assert res.status_code == 202
    mock_send_email.assert_called_once()


async def test_request_verify_token_already_verified(
    client: AsyncClient, mock_send_email: AsyncMock
) -> None:
    await register_user(client)
    verify_token = mock_send_email.call_args[0][1]
    await client.post("/auth/verify", json={"token": verify_token})
    mock_send_email.reset_mock()

    # fastapi-users devuelve 202 silencioso para no revelar el estado de verificacion
    res = await client.post(
        "/auth/request-verify-token", json={"email": "user@example.com"}
    )
    assert res.status_code == 202
    mock_send_email.assert_not_called()
