"""Tests del flujo de registro multi-paso con OTP y Google."""
from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.config import settings
from fitapp.models.email_otp import EmailOTP
from fitapp.models.user import User
from fitapp.services.otp import create_google_registration_token, create_verified_token
from tests.conftest import _SessionFactory, login_user


# ── Helpers ───────────────────────────────────────────────────────────────────

_PROFILE = {
    "first_name": "Ana",
    "last_name": "García",
    "birth_date": "1990-06-15",
    "gender": "mujer",
}


async def _send_otp(client: AsyncClient, email: str = "otp@example.com") -> None:
    with patch("fitapp.routers.register.send_otp_email", new_callable=AsyncMock):
        res = await client.post("/auth/register/send-otp", json={"email": email})
    assert res.status_code == 200, res.text


async def _get_otp_code(email: str = "otp@example.com") -> str:
    async with _SessionFactory() as session:
        result = await session.execute(
            select(EmailOTP).where(EmailOTP.email == email, EmailOTP.used.is_(False))
        )
        return result.scalar_one().code


async def _verify_otp(client: AsyncClient, email: str = "otp@example.com") -> str:
    await _send_otp(client, email)
    code = await _get_otp_code(email)
    res = await client.post("/auth/register/verify-otp", json={"email": email, "code": code})
    assert res.status_code == 200, res.text
    return res.json()["verified_token"]


async def _create_user_in_db(email: str) -> User:
    """Crea un usuario directamente en BD para tests que lo necesiten."""
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


# ── POST /auth/register/send-otp ──────────────────────────────────────────────

async def test_send_otp_returns_ok(client: AsyncClient) -> None:
    with patch("fitapp.routers.register.send_otp_email", new_callable=AsyncMock) as mock_email:
        res = await client.post("/auth/register/send-otp", json={"email": "a@example.com"})
    assert res.status_code == 200
    assert res.json()["message"] == "OTP enviado"
    mock_email.assert_awaited_once()


async def test_send_otp_stores_in_db(client: AsyncClient) -> None:
    with patch("fitapp.routers.register.send_otp_email", new_callable=AsyncMock):
        await client.post("/auth/register/send-otp", json={"email": "b@example.com"})
    async with _SessionFactory() as session:
        result = await session.execute(select(EmailOTP).where(EmailOTP.email == "b@example.com"))
        otp = result.scalar_one_or_none()
    assert otp is not None
    assert otp.used is False
    assert otp.expires_at > datetime.datetime.now(datetime.timezone.utc)


async def test_send_otp_replaces_previous(client: AsyncClient) -> None:
    with patch("fitapp.routers.register.send_otp_email", new_callable=AsyncMock):
        await client.post("/auth/register/send-otp", json={"email": "c@example.com"})
        code1 = await _get_otp_code("c@example.com")
        await client.post("/auth/register/send-otp", json={"email": "c@example.com"})
    async with _SessionFactory() as session:
        result = await session.execute(
            select(EmailOTP).where(EmailOTP.email == "c@example.com", EmailOTP.used.is_(False))
        )
        otps = result.scalars().all()
    assert len(otps) == 1
    assert otps[0].code != code1


# ── POST /auth/register/verify-otp ───────────────────────────────────────────

async def test_verify_otp_correct_code_returns_token(client: AsyncClient) -> None:
    await _send_otp(client, "d@example.com")
    code = await _get_otp_code("d@example.com")
    res = await client.post("/auth/register/verify-otp", json={"email": "d@example.com", "code": code})
    assert res.status_code == 200
    assert res.json()["verified_token"] != ""


async def test_verify_otp_wrong_code_returns_400(client: AsyncClient) -> None:
    await _send_otp(client, "e@example.com")
    res = await client.post("/auth/register/verify-otp", json={"email": "e@example.com", "code": "000000"})
    assert res.status_code == 400
    assert "incorrecto" in res.json()["detail"].lower()


async def test_verify_otp_used_code_returns_400(client: AsyncClient) -> None:
    await _send_otp(client, "f@example.com")
    code = await _get_otp_code("f@example.com")
    await client.post("/auth/register/verify-otp", json={"email": "f@example.com", "code": code})
    res = await client.post("/auth/register/verify-otp", json={"email": "f@example.com", "code": code})
    assert res.status_code == 400


async def test_verify_otp_expired_code_returns_400(client: AsyncClient) -> None:
    await _send_otp(client, "g@example.com")
    async with _SessionFactory() as session:
        result = await session.execute(select(EmailOTP).where(EmailOTP.email == "g@example.com"))
        otp = result.scalar_one()
        code = otp.code
        otp.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
        await session.commit()
    res = await client.post("/auth/register/verify-otp", json={"email": "g@example.com", "code": code})
    assert res.status_code == 400


# ── POST /auth/register/complete ─────────────────────────────────────────────

async def test_complete_registration_success(client: AsyncClient) -> None:
    token = await _verify_otp(client, "h@example.com")
    res = await client.post(
        "/auth/register/complete",
        json={"verified_token": token, "password": "pass1234", **_PROFILE},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "h@example.com"
    assert body["first_name"] == _PROFILE["first_name"]
    assert body["last_name"] == _PROFILE["last_name"]
    assert body["is_verified"] is True


async def test_complete_registration_invalid_token_returns_400(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/register/complete",
        json={"verified_token": "not.valid.token", "password": "pass1234", **_PROFILE},
    )
    assert res.status_code == 400
    assert "inválido" in res.json()["detail"].lower()


async def test_complete_registration_expired_token_returns_400(client: AsyncClient) -> None:
    expired = pyjwt.encode(
        {"sub": "i@example.com", "type": "otp_verified", "exp": 1},
        settings.jwt_secret,
        algorithm="HS256",
    )
    res = await client.post(
        "/auth/register/complete",
        json={"verified_token": expired, "password": "pass1234", **_PROFILE},
    )
    assert res.status_code == 400


async def test_complete_registration_duplicate_email_returns_409(client: AsyncClient) -> None:
    token = await _verify_otp(client, "j@example.com")
    await client.post(
        "/auth/register/complete",
        json={"verified_token": token, "password": "pass1234", **_PROFILE},
    )
    token2 = create_verified_token("j@example.com")
    res = await client.post(
        "/auth/register/complete",
        json={"verified_token": token2, "password": "pass1234", **_PROFILE},
    )
    assert res.status_code == 409


async def test_complete_registration_short_password_returns_400(client: AsyncClient) -> None:
    token = await _verify_otp(client, "k@example.com")
    res = await client.post(
        "/auth/register/complete",
        json={"verified_token": token, "password": "short", **_PROFILE},
    )
    assert res.status_code == 400


async def test_complete_registration_user_can_login(client: AsyncClient) -> None:
    token = await _verify_otp(client, "l@example.com")
    await client.post(
        "/auth/register/complete",
        json={"verified_token": token, "password": "pass1234", **_PROFILE},
    )
    jwt_token = await login_user(client, "l@example.com")
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "l@example.com"
    assert me.json()["first_name"] == _PROFILE["first_name"]
    assert me.json()["gender"] == _PROFILE["gender"]


async def test_complete_registration_profile_fields_saved(client: AsyncClient) -> None:
    token = await _verify_otp(client, "m@example.com")
    await client.post(
        "/auth/register/complete",
        json={"verified_token": token, "password": "pass1234", **_PROFILE},
    )
    async with _SessionFactory() as session:
        result = await session.execute(select(User).where(User.email == "m@example.com"))
        user = result.unique().scalar_one()
    assert user.birth_date == datetime.date(1990, 6, 15)
    assert user.gender.value == "mujer"


# ── POST /auth/register/complete-google ──────────────────────────────────────

async def test_complete_google_invalid_token(client: AsyncClient) -> None:
    res = await client.post(
        "/auth/register/complete-google",
        json={"google_token": "not.a.valid.token", **_PROFILE},
    )
    assert res.status_code == 400
    assert "inválido" in res.json()["detail"].lower()


async def test_complete_google_expired_token(client: AsyncClient) -> None:
    expired = pyjwt.encode(
        {
            "sub": "gexp@example.com",
            "type": "google_registration",
            "first_name": "X",
            "last_name": "Y",
            "account_id": "id",
            "google_access_token": "tok",
            "expires_at": None,
            "refresh_token": None,
            "exp": 1,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    res = await client.post(
        "/auth/register/complete-google",
        json={"google_token": expired, **_PROFILE},
    )
    assert res.status_code == 400


async def test_complete_google_success(client: AsyncClient) -> None:
    """Registro con Google exitoso: crea usuario y devuelve JWT de sesión."""
    from fitapp.auth.users import get_user_manager
    from fitapp.main import app

    google_token = create_google_registration_token(
        email="gmock@example.com",
        first_name="Google",
        last_name="User",
        account_id="g_account_123",
        google_access_token="fake_g_access",
        expires_at=None,
        refresh_token=None,
    )

    # Creamos el usuario en BD para que el SELECT de `complete_google_registration` lo encuentre
    db_user = await _create_user_in_db("gmock@example.com")

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
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
    finally:
        app.dependency_overrides.pop(get_user_manager, None)

    # Verificar que el token es válido con el user_manager real
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "gmock@example.com"


async def test_complete_google_profile_fields_saved(client: AsyncClient) -> None:
    """El nombre viene del token Google; birth_date y gender quedan null."""
    from fitapp.auth.users import get_user_manager
    from fitapp.main import app

    google_token = create_google_registration_token(
        email="gprofile@example.com",
        first_name="Pedro",
        last_name="López",
        account_id="g_acc_456",
        google_access_token="fake",
        expires_at=None,
        refresh_token=None,
    )
    db_user = await _create_user_in_db("gprofile@example.com")

    async def _override_um() -> AsyncGenerator:
        class _FakeUM:
            async def oauth_callback(self, **kw):
                return db_user
        yield _FakeUM()

    app.dependency_overrides[get_user_manager] = _override_um
    try:
        await client.post(
            "/auth/register/complete-google",
            json={"google_token": google_token},
        )
    finally:
        app.dependency_overrides.pop(get_user_manager, None)

    async with _SessionFactory() as session:
        result = await session.execute(select(User).where(User.email == "gprofile@example.com"))
        user = result.unique().scalar_one()
    assert user.first_name == "Pedro"
    assert user.last_name == "López"
    assert user.birth_date is None
    assert user.gender is None
