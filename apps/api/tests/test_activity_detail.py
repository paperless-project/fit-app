"""Tests del endpoint GET /activities/{id}."""
from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from tests.conftest import login_user, register_user

_SAMPLE_FIT = Path("/activities/240714102315.fit")


async def _upload(client: AsyncClient, headers: dict) -> dict:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers=headers,
        )
    assert res.status_code == 201
    return res.json()


async def test_get_detail_returns_records_and_laps(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    activity = await _upload(client, headers)
    activity_id = activity["id"]

    res = await client.get(f"/activities/{activity_id}", headers=headers)
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == activity_id
    assert data["file_name"] == "240714102315.fit"
    assert isinstance(data["records"], list)
    assert len(data["records"]) > 100

    # Cada record tiene los campos esperados
    rec = data["records"][0]
    assert "ts" in rec
    assert "lat" in rec
    assert "lon" in rec
    assert "altitude_m" in rec
    assert "speed_mps" in rec


async def test_get_detail_records_have_gps(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    activity = await _upload(client, headers)
    res = await client.get(f"/activities/{activity['id']}", headers=headers)

    records = res.json()["records"]
    gps_records = [r for r in records if r["lat"] is not None and r["lon"] is not None]
    assert len(gps_records) > 100


async def test_get_detail_not_found(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)

    import uuid
    res = await client.get(
        f"/activities/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


async def test_get_detail_other_user_forbidden(client: AsyncClient) -> None:
    await register_user(client, "a@example.com")
    await register_user(client, "b@example.com")
    token_a = await login_user(client, "a@example.com")
    token_b = await login_user(client, "b@example.com")

    activity = await _upload(client, {"Authorization": f"Bearer {token_a}"})
    res = await client.get(
        f"/activities/{activity['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404


async def test_get_detail_requires_auth(client: AsyncClient) -> None:
    import uuid
    res = await client.get(f"/activities/{uuid.uuid4()}")
    assert res.status_code == 401
