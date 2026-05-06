"""Tests del endpoint /auth/jwt-remember/login (sesion de 15 dias)."""
from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from tests.conftest import register_user

_REMEMBER_LIFETIME = 15 * 24 * 3600  # 15 días en segundos


async def _login(client: AsyncClient, endpoint: str, email: str, password: str) -> dict:
    res = await client.post(
        endpoint,
        content=f"username={email}&password={password}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _decode_exp(token: str) -> int:
    """Extrae el campo 'exp' del payload JWT sin verificar firma."""
    import base64
    import json

    payload_b64 = token.split(".")[1]
    # Padding
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))["exp"]


async def test_remember_me_endpoint_exists(client: AsyncClient) -> None:
    await register_user(client)
    body = await _login(client, "/auth/jwt-remember/login", "user@example.com", "pass1234")
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_remember_me_token_lifetime_is_15_days(client: AsyncClient) -> None:
    await register_user(client)
    body = await _login(client, "/auth/jwt-remember/login", "user@example.com", "pass1234")
    token = body["access_token"]
    exp = _decode_exp(token)
    remaining = exp - int(time.time())
    # El token debe expirar en ~15 días (permitimos ±60 s de margen)
    assert abs(remaining - _REMEMBER_LIFETIME) < 60


async def test_standard_token_lifetime_is_short(client: AsyncClient) -> None:
    await register_user(client)
    body = await _login(client, "/auth/jwt/login", "user@example.com", "pass1234")
    token = body["access_token"]
    exp = _decode_exp(token)
    remaining = exp - int(time.time())
    # El token estándar no debe durar 15 días
    assert remaining < _REMEMBER_LIFETIME - 3600


async def test_remember_me_wrong_password(client: AsyncClient) -> None:
    await register_user(client)
    res = await client.post(
        "/auth/jwt-remember/login",
        content="username=user@example.com&password=wrong",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 400
    assert "LOGIN_BAD_CREDENTIALS" in res.text


async def test_remember_me_token_grants_access(client: AsyncClient) -> None:
    await register_user(client, "rme@example.com")
    body = await _login(client, "/auth/jwt-remember/login", "rme@example.com", "pass1234")
    token = body["access_token"]
    res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "rme@example.com"
