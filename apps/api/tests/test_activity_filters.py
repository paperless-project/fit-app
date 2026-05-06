"""Tests de filtrado en GET /activities/."""
from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient

from tests.conftest import login_user, register_user

_SAMPLE_FIT = Path("/activities/240714102315.fit")


async def _upload(client: AsyncClient, token: str) -> dict:
    with _SAMPLE_FIT.open("rb") as f:
        res = await client.post(
            "/activities/upload",
            files={"file": ("240714102315.fit", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    return res.json()


async def test_filter_by_sport_match(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)
    sport = activity["sport"]

    res = await client.get(
        f"/activities/?sport={sport}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


async def test_filter_by_sport_no_match(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    await _upload(client, token)

    res = await client.get(
        "/activities/?sport=running",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


async def test_filter_by_date_from_includes(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)
    date_str = activity["started_at"][:10]

    res = await client.get(
        f"/activities/?date_from={date_str}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


async def test_filter_by_date_to_excludes(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)
    date_str = activity["started_at"][:10]

    res = await client.get(
        f"/activities/?date_to=2000-01-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == []


async def test_filter_by_date_range_includes(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)
    date_str = activity["started_at"][:10]

    res = await client.get(
        f"/activities/?date_from={date_str}&date_to={date_str}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


async def test_filter_by_name_search(client: AsyncClient) -> None:
    await register_user(client)
    token = await login_user(client)
    activity = await _upload(client, token)

    # Patch activity with a known name first
    act_id = activity["id"]
    await client.patch(
        f"/activities/{act_id}",
        json={"name": "Vuelta por la costa"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = await client.get(
        "/activities/?q=costa",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    res_no_match = await client.get(
        "/activities/?q=montaña",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_no_match.json() == []


async def test_filter_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/activities/?sport=cycling")
    assert res.status_code == 401
