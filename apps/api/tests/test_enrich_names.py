"""Tests del job de enriquecimiento de nombres y del endpoint POST /activities/enrich-names."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.conftest import _SessionFactory, login_user, register_user
from fitapp.services.activity_service import enrich_activity_name

_SAMPLE_FIT = __import__("pathlib").Path("/activities/240714102315.fit")


async def _upload(client: AsyncClient, token: str) -> dict:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def enrich_via_test_db(mock_enrich_bg: AsyncMock):
    """Redirige _enrich_name_bg para que use la BD de test en lugar de SessionLocal.

    Como el side_effect se ejecuta dentro de la llamada a client.post() (contexto
    ASGI), comparte el mismo event loop que el motor de test — evita el error
    'Future attached to a different loop'.
    """
    async def _run(activity_id: uuid.UUID) -> None:
        async with _SessionFactory() as db:
            await enrich_activity_name(db, activity_id)

    mock_enrich_bg.side_effect = _run
    return mock_enrich_bg


# ── Enriquecimiento via background task ───────────────────────────────────────

async def test_upload_enriches_name_via_background_task(
    client: AsyncClient,
    enrich_via_test_db,
    mock_geocoding: AsyncMock,
) -> None:
    """Tras un upload, el background task rellena el nombre."""
    mock_geocoding.return_value = "Castillo de Olite desde Tafalla"

    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["name"] == "Castillo de Olite desde Tafalla"


async def test_upload_name_stays_null_when_geocoding_fails(
    client: AsyncClient,
    enrich_via_test_db,
) -> None:
    """Si el geocoding devuelve None, el nombre sigue siendo null."""
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["name"] is None


async def test_upload_queues_enrich_bg_task(
    client: AsyncClient,
    mock_enrich_bg: AsyncMock,
) -> None:
    """El upload encola _enrich_name_bg exactamente una vez."""
    await register_user(client)
    token = await login_user(client)
    await _upload(client, token)

    mock_enrich_bg.assert_awaited_once()


# ── force=True sobreescribe nombre existente ──────────────────────────────────

async def test_enrich_force_overwrites_existing_name(
    client: AsyncClient,
    enrich_via_test_db,
    mock_geocoding: AsyncMock,
) -> None:
    """force=True sobreescribe aunque ya haya nombre."""
    mock_geocoding.return_value = "Nombre geocodificado"

    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    # Poner nombre manualmente, luego re-enriquecer con force
    await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Nombre original"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Llamar enrich_activity_name con force directamente dentro de este contexto:
    # lo hacemos via side_effect del próximo upload no es posible, así que
    # llamamos a la función directamente — dentro de la misma task del test
    # (no hay ambigüedad de loop porque no hay transferencia cross-loop aquí).
    async with _SessionFactory() as db:
        updated = await enrich_activity_name(db, uuid.UUID(activity["id"]), force=True)

    assert updated is True

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["name"] == "Nombre geocodificado"


async def test_enrich_skips_when_name_exists_and_no_force(
    client: AsyncClient,
    enrich_via_test_db,
    mock_geocoding: AsyncMock,
) -> None:
    """force=False (por defecto) no sobreescribe nombre existente."""
    mock_geocoding.return_value = "No deberia verse"

    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Nombre original"},
        headers={"Authorization": f"Bearer {token}"},
    )

    async with _SessionFactory() as db:
        updated = await enrich_activity_name(db, uuid.UUID(activity["id"]), force=False)

    assert updated is False

    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["name"] == "Nombre original"


async def test_enrich_returns_false_for_nonexistent_activity(
    client: AsyncClient,
) -> None:
    async with _SessionFactory() as db:
        updated = await enrich_activity_name(db, uuid.uuid4())
    assert updated is False


# ── POST /activities/enrich-names ─────────────────────────────────────────────

async def test_enrich_names_endpoint_queues_null_activities(
    client: AsyncClient,
) -> None:
    await register_user(client)
    token = await login_user(client)
    await _upload(client, token)

    res = await client.post(
        "/activities/enrich-names",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["queued"] == 1


async def test_enrich_names_endpoint_zero_when_all_named(
    client: AsyncClient,
) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    await client.patch(
        f"/activities/{activity['id']}",
        json={"name": "Ya tiene nombre"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = await client.post(
        "/activities/enrich-names",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.json()["queued"] == 0


async def test_enrich_names_endpoint_requires_auth(client: AsyncClient) -> None:
    res = await client.post("/activities/enrich-names")
    assert res.status_code == 401


async def test_enrich_names_endpoint_isolation(client: AsyncClient) -> None:
    """Cada usuario solo ve sus propias actividades pendientes."""
    await register_user(client, "u1@example.com")
    await register_user(client, "u2@example.com")
    t1 = await login_user(client, "u1@example.com")
    t2 = await login_user(client, "u2@example.com")
    await _upload(client, t1)

    res = await client.post(
        "/activities/enrich-names",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert res.json()["queued"] == 0
