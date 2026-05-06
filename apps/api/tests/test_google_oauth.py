"""Tests del flujo OAuth2 de Google: authorize y callback."""
from __future__ import annotations

import time
import urllib.parse
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import AsyncClient

from fitapp.auth.users import google_oauth_client
from fitapp.config import settings

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_state_and_csrf(
    client: AsyncClient, flow: str = "login"
) -> tuple[str, str]:
    """Llama a /authorize y devuelve (state_jwt, csrf_cookie_value)."""
    res = await client.get("/auth/google/authorize", params={"flow": flow})
    assert res.status_code == 200
    url = res.json()["authorization_url"]
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    state = params["state"]
    csrf = next(v for k, v in res.cookies.items() if "fastapiusers" in k.lower())
    return state, csrf


def _mock_google(access_token: str = "g_token", account_id: str = "gid_1", email: str = "google@example.com"):
    """Parchea get_access_token y get_id_email para evitar llamadas reales a Google."""
    return (
        patch.object(google_oauth_client, "get_access_token",
                     new_callable=AsyncMock,
                     return_value={"access_token": access_token, "token_type": "bearer"}),
        patch.object(google_oauth_client, "get_id_email",
                     new_callable=AsyncMock,
                     return_value=(account_id, email)),
    )


# ── /auth/google/authorize ────────────────────────────────────────────────────

async def test_google_authorize_returns_authorization_url(client: AsyncClient) -> None:
    res = await client.get("/auth/google/authorize",
                           params=[("scopes", "openid"), ("scopes", "email"), ("scopes", "profile")])
    assert res.status_code == 200, res.text
    assert "authorization_url" in res.json()
    assert res.json()["authorization_url"].startswith("https://accounts.google.com/")


async def test_google_authorize_url_contains_scopes(client: AsyncClient) -> None:
    res = await client.get("/auth/google/authorize",
                           params=[("scopes", "openid"), ("scopes", "email"), ("scopes", "profile")])
    url = res.json()["authorization_url"]
    assert "email" in url
    assert "profile" in url


async def test_google_authorize_redirect_uri_points_to_backend(client: AsyncClient) -> None:
    """El redirect_uri debe apuntar al backend, nunca al frontend."""
    res = await client.get("/auth/google/authorize")
    url = res.json()["authorization_url"]
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    redirect_uri = params["redirect_uri"]
    assert redirect_uri == f"{settings.api_url}/auth/google/callback", (
        f"redirect_uri incorrecto: {redirect_uri!r} — debe ser {settings.api_url}/auth/google/callback"
    )
    assert settings.frontend_url not in redirect_uri, "redirect_uri no debe apuntar al frontend"


async def test_google_authorize_sets_csrf_cookie(client: AsyncClient) -> None:
    res = await client.get("/auth/google/authorize")
    assert res.status_code == 200
    assert any("fastapiusers" in k.lower() for k in res.cookies)


async def test_google_authorize_state_contains_flow(client: AsyncClient) -> None:
    """El state JWT generado por /authorize incluye el campo 'flow'."""
    for flow in ("login", "register"):
        res = await client.get("/auth/google/authorize", params={"flow": flow})
        url = res.json()["authorization_url"]
        encoded_state = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["state"]
        payload = jwt.decode(encoded_state, settings.jwt_secret, algorithms=["HS256"],
                             audience="fastapi-users:oauth-state")
        assert payload.get("flow") == flow, f"flow esperado={flow!r}, obtenido={payload.get('flow')!r}"


# ── /auth/google/callback — casos de error ───────────────────────────────────

async def test_google_callback_rejects_missing_state(client: AsyncClient) -> None:
    """Sin state en la URL → 422 (parámetro obligatorio)."""
    mock_token = {"access_token": "tok", "token_type": "bearer"}
    with patch.object(google_oauth_client, "get_access_token",
                      new_callable=AsyncMock, return_value=mock_token):
        res = await client.get("/auth/google/callback", params={"code": "fake_code"})
    assert res.status_code == 422


async def test_google_callback_rejects_invalid_state(client: AsyncClient) -> None:
    """State JWT malformado → 400."""
    mock_token = {"access_token": "tok", "token_type": "bearer"}
    with patch.object(google_oauth_client, "get_access_token",
                      new_callable=AsyncMock, return_value=mock_token):
        res = await client.get("/auth/google/callback",
                               params={"code": "fake_code", "state": "not.a.valid.jwt"})
    assert res.status_code == 400
    assert "STATE" in res.json()["detail"]


async def test_google_callback_rejects_csrf_mismatch(client: AsyncClient) -> None:
    """State JWT válido pero cookie CSRF ausente/incorrecta → 400."""
    state = jwt.encode(
        {"csrftoken": "legit", "aud": "fastapi-users:oauth-state", "exp": int(time.time()) + 3600},
        settings.jwt_secret, algorithm="HS256",
    )
    mock_token = {"access_token": "tok", "token_type": "bearer"}
    with patch.object(google_oauth_client, "get_access_token",
                      new_callable=AsyncMock, return_value=mock_token):
        res = await client.get("/auth/google/callback",
                               params={"code": "fake", "state": state})
    assert res.status_code == 400
    assert "CSRF" in res.json()["detail"]


# ── Implementación: endpoint OpenID correcto ──────────────────────────────────

async def test_google_uses_openid_userinfo_not_people_api(client: AsyncClient) -> None:
    """get_id_email debe usar el endpoint OpenID (/oauth2/v2/userinfo), no la People API."""
    called_urls: list[str] = []

    class _TracingCtx:
        async def __aenter__(self):
            import httpx
            class _R(httpx.AsyncClient):
                async def get(self, url, **kw):  # type: ignore[override]
                    called_urls.append(str(url))
                    return httpx.Response(200, json={"id": "123", "email": "x@x.com"})
            return _R()
        async def __aexit__(self, *_): ...

    with patch.object(google_oauth_client, "get_httpx_client", return_value=_TracingCtx()):
        await google_oauth_client.get_id_email("fake_token")

    assert any("oauth2/v2/userinfo" in u for u in called_urls), (
        f"Debe llamar al endpoint OpenID estándar, llamó a: {called_urls}"
    )
    assert not any("people.googleapis.com" in u for u in called_urls), (
        "No debe usar People API (requiere habilitación extra en Google Console)"
    )


# ── Flujo completo con mocks ──────────────────────────────────────────────────

async def test_google_callback_network_error_redirects_to_login(client: AsyncClient) -> None:
    """Timeout/error de red en get_id_email → redirige a /login con google_error (no 500)."""
    import httpx as _httpx
    state, csrf = await _get_state_and_csrf(client, flow="login")

    with patch.object(google_oauth_client, "get_access_token",
                      new_callable=AsyncMock,
                      return_value={"access_token": "tok", "token_type": "bearer"}):
        with patch.object(google_oauth_client, "get_id_email",
                          new_callable=AsyncMock,
                          side_effect=_httpx.ReadTimeout("timeout")):
            res = await client.get(
                "/auth/google/callback",
                params={"code": "code", "state": state},
                cookies={"fastapiusersoauthcsrf": csrf},
                follow_redirects=False,
            )

    assert res.status_code == 302, res.text
    location = res.headers["location"]
    assert "google_error" in location
    assert "/login" in location


async def test_google_callback_login_flow_unknown_profile_redirects_to_error(client: AsyncClient) -> None:
    """flow=login + perfil sin cuenta → redirige a /login con google_error (NO crea usuario)."""
    state, csrf = await _get_state_and_csrf(client, flow="login")

    p1, p2 = _mock_google(account_id="unknown_login_gid", email="newuser_login@example.com")
    with p1, p2:
        res = await client.get(
            "/auth/google/callback",
            params={"code": "code", "state": state},
            cookies={"fastapiusersoauthcsrf": csrf},
            follow_redirects=False,
        )

    assert res.status_code == 302, res.text
    location = res.headers["location"]
    assert "/login" in location
    assert "google_error" in location
    # Verificar que NO redirige a registro (no crea usuario)
    assert "/register" not in location


async def test_google_callback_register_flow_unknown_profile_redirects_to_register(client: AsyncClient) -> None:
    """flow=register + perfil sin cuenta → redirige a /register con google_token para crear cuenta."""
    state, csrf = await _get_state_and_csrf(client, flow="register")

    p1, p2 = _mock_google(account_id="unknown_reg_gid", email="newuser_reg@example.com")
    with p1, p2:
        with patch.object(
            google_oauth_client, "get_profile",
            new_callable=AsyncMock,
            return_value={"given_name": "Test", "family_name": "User"},
        ):
            res = await client.get(
                "/auth/google/callback",
                params={"code": "code", "state": state},
                cookies={"fastapiusersoauthcsrf": csrf},
                follow_redirects=False,
            )

    assert res.status_code == 302, res.text
    location = res.headers["location"]
    assert "/register" in location
    assert "google_token" in location
    assert "/login" not in location


async def test_google_callback_existing_user_gets_token(client: AsyncClient) -> None:
    """Usuario registrado con email/password puede acceder con Google si el email coincide."""
    from tests.conftest import register_user
    await register_user(client, "existing@example.com")

    state, csrf = await _get_state_and_csrf(client, flow="login")
    p1, p2 = _mock_google(account_id="gid_existing", email="existing@example.com")
    with p1, p2:
        res = await client.get(
            "/auth/google/callback",
            params={"code": "code", "state": state},
            cookies={"fastapiusersoauthcsrf": csrf},
            follow_redirects=False,
        )

    assert res.status_code == 302, res.text
    location = res.headers["location"]
    assert "access_token=" in location
    assert settings.frontend_url in location


async def test_google_callback_second_login_reuses_existing_user(client: AsyncClient) -> None:
    """Segundo login con el mismo perfil Google reutiliza el usuario existente."""
    from tests.conftest import register_user
    await register_user(client, "linked@example.com")

    async def _login_with_google() -> str:
        state, csrf = await _get_state_and_csrf(client, flow="login")
        p1, p2 = _mock_google(account_id="same_gid", email="linked@example.com")
        with p1, p2:
            res = await client.get(
                "/auth/google/callback",
                params={"code": "code", "state": state},
                cookies={"fastapiusersoauthcsrf": csrf},
                follow_redirects=False,
            )
        assert res.status_code == 302, res.text
        return urllib.parse.parse_qs(
            urllib.parse.urlparse(res.headers["location"]).query
        )["access_token"][0]

    token1 = await _login_with_google()
    token2 = await _login_with_google()

    me1 = await client.get("/users/me", headers={"Authorization": f"Bearer {token1}"})
    me2 = await client.get("/users/me", headers={"Authorization": f"Bearer {token2}"})
    assert me1.json()["id"] == me2.json()["id"]
