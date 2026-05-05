"""Fixtures comunes de pytest. (se ampliara con BD de test en Fase 1)"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fitapp.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
