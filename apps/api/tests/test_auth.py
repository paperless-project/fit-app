"""Tests del flujo de autenticacion (register, login, /users/me, logout)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login_user, register_user


# ── Register ────────────────────────────────────────────────────────────────
async def test_register_success(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "pass1234"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "new@example.com"
    assert body["is_active"] is True
    assert "hashed_password" not in body


async def test_register_duplicate_email(client: AsyncClient) -> None:
    await register_user(client, "dup@example.com")
    res = await client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "pass1234"},
    )
    assert res.status_code == 400
    assert "REGISTER_USER_ALREADY_EXISTS" in res.text


async def test_register_invalid_email(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "pass1234"},
    )
    assert res.status_code == 422


async def test_register_short_password(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert res.status_code == 400
    assert "REGISTER_INVALID_PASSWORD" in res.text


# ── Login ───────────────────────────────────────────────────────────────────
async def test_login_success(client: AsyncClient) -> None:
    await register_user(client)
    res = await client.post(
        "/auth/jwt/login",
        content="username=user@example.com&password=pass1234",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await register_user(client)
    res = await client.post(
        "/auth/jwt/login",
        content="username=user@example.com&password=wrong",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 400
    assert "LOGIN_BAD_CREDENTIALS" in res.text


async def test_login_unknown_email(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/jwt/login",
        content="username=ghost@example.com&password=pass1234",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 400
    assert "LOGIN_BAD_CREDENTIALS" in res.text


# ── /users/me ────────────────────────────────────────────────────────────────
async def test_me_returns_current_user(client: AsyncClient) -> None:
    await register_user(client, "me@example.com")
    token = await login_user(client, "me@example.com")

    res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


async def test_me_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/users/me")
    assert res.status_code == 401


async def test_me_invalid_token(client: AsyncClient) -> None:
    res = await client.get("/users/me", headers={"Authorization": "Bearer token.invalido"})
    assert res.status_code == 401


# ── Logout ───────────────────────────────────────────────────────────────────
async def test_logout_success(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    res = await client.post("/auth/jwt/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204


async def test_logout_requires_auth(client: AsyncClient) -> None:
    res = await client.post("/auth/jwt/logout")
    assert res.status_code == 401
