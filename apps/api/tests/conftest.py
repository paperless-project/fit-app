"""Fixtures de pytest con base de datos de test dedicada (fitapp_test)."""
from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncGenerator

from unittest.mock import AsyncMock, patch

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from fitapp.config import settings
from fitapp.db import get_session
from fitapp.main import app

# ── Base de datos de test ───────────────────────────────────────────────────
_TEST_DB = "fitapp_test"
_TEST_ASYNC_URL = settings.async_database_url.rsplit("/", 1)[0] + f"/{_TEST_DB}"

# NullPool: sin reutilizacion de conexiones entre tests → sin "operation in progress"
_engine = create_async_engine(_TEST_ASYNC_URL, echo=False, poolclass=NullPool)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)

_APP_TABLES = ["records", "laps", "activities", "oauth_account", "users"]


# ── Creacion del schema (una vez por sesion de pytest) ──────────────────────
@pytest.fixture(scope="session", autouse=True)
def _setup_test_db() -> None:
    conn_str = (
        f"host={settings.postgres_host} port={settings.postgres_port} "
        f"user={settings.postgres_user} password={settings.postgres_password} "
        f"dbname={settings.postgres_db}"
    )
    with psycopg.connect(conn_str, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {_TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {_TEST_DB}")

    env = {**os.environ, "POSTGRES_DB": _TEST_DB}
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="/app",
        env=env,
        check=True,
        capture_output=True,
    )


# ── Mock de envio de email (nunca conecta a SMTP real en tests) ─────────────
@pytest.fixture(autouse=True)
def mock_send_email():
    with patch("fitapp.auth.users.send_verification_email", new_callable=AsyncMock) as mock:
        yield mock


# ── Mock de geocoding (nunca llama a Nominatim en tests) ────────────────────
@pytest.fixture(autouse=True)
def mock_geocoding():
    with patch(
        "fitapp.services.activity_service.generate_activity_name",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock:
        yield mock


# ── Mock de tarea de fondo de enriquecimiento (evita sesion propia en tests) ─
# Se parchea donde se USA (el router importa _enrich_name_bg por nombre directo),
# no donde está definida, para que background_tasks.add_task reciba el mock.
@pytest.fixture(autouse=True)
def mock_enrich_bg():
    with patch(
        "fitapp.routers.activities._enrich_name_bg",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


# ── Limpieza de tablas entre tests ─────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncGenerator[None, None]:
    yield
    tables = ", ".join(_APP_TABLES)
    async with _engine.connect() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {tables} CASCADE"))
        await conn.commit()


# ── Cliente HTTP con override de dependencia ────────────────────────────────
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with _SessionFactory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers reutilizables ───────────────────────────────────────────────────
async def register_user(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = "pass1234",
) -> dict:
    res = await client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()


async def login_user(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = "pass1234",
) -> str:
    res = await client.post(
        "/auth/jwt/login",
        content=f"username={email}&password={password}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
