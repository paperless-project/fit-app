"""Tests de DELETE /users/me."""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from fitapp.auth.users import get_user_manager
from fitapp.main import app
from fitapp.models.user import User
from fitapp.services.otp import create_google_registration_token
from tests.conftest import _SessionFactory, login_user, register_user

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


# ── Borrado de usuarios registrados con Google ────────────────────────────────

async def _create_google_user_in_db(email: str) -> User:
    async with _SessionFactory() as session:
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="!",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _register_with_google(client: AsyncClient, email: str) -> str:
    """Registra un usuario vía Google y devuelve el access_token de sesión."""
    google_token = create_google_registration_token(
        email=email,
        first_name="Google",
        last_name="User",
        account_id=f"gid_{email}",
        google_access_token="fake_access",
        expires_at=None,
        refresh_token=None,
    )
    db_user = await _create_google_user_in_db(email)

    async def _override_um() -> AsyncGenerator:
        class _FakeUM:
            async def oauth_callback(self, **kw):
                return db_user
        yield _FakeUM()

    app.dependency_overrides[get_user_manager] = _override_um
    try:
        res = await client.post(
            "/auth/register/complete-google",
            json={"google_token": google_token},
        )
        assert res.status_code == 201, res.text
        return res.json()["access_token"]
    finally:
        app.dependency_overrides.pop(get_user_manager, None)


async def test_delete_google_account_ok(client: AsyncClient) -> None:
    """Un usuario registrado con Google puede borrar su cuenta."""
    token = await _register_with_google(client, "gdel@example.com")

    res = await _delete_account(client, token, confirm=True)
    assert res.status_code == 204

    res = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_delete_google_account_cascades_activities(client: AsyncClient) -> None:
    """Borrar cuenta Google elimina también sus actividades."""
    token = await _register_with_google(client, "gdel2@example.com")
    activity = await _upload(client, token)

    res = await _delete_account(client, token, confirm=True)
    assert res.status_code == 204

    # Otro usuario no puede acceder a la actividad borrada
    await register_user(client, "other2@example.com")
    other_token = await login_user(client, "other2@example.com")
    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res.status_code == 404


async def test_delete_google_account_requires_confirmation(client: AsyncClient) -> None:
    """confirm=False rechazado también para usuarios Google."""
    token = await _register_with_google(client, "gdel3@example.com")

    res = await _delete_account(client, token, confirm=False)
    assert res.status_code == 400
    assert res.json()["detail"] == "CONFIRMATION_REQUIRED"
