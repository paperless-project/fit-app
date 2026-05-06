"""Callback OAuth2 de Google: intercambia el code por JWT y redirige al frontend."""
from __future__ import annotations

import secrets
import urllib.parse

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_users.exceptions import UserNotExists
from fastapi_users.router.oauth import (
    CSRF_TOKEN_COOKIE_NAME,
    CSRF_TOKEN_KEY,
    STATE_TOKEN_AUDIENCE,
    OAuth2AuthorizeCallback,
    decode_jwt,
)

from fitapp.auth.users import auth_backend, get_user_manager, google_oauth_client
from fitapp.config import settings

BACKEND_CALLBACK_URL = f"{settings.api_url}/auth/google/callback"

_oauth2_callback = OAuth2AuthorizeCallback(
    google_oauth_client,
    redirect_url=BACKEND_CALLBACK_URL,
)

router = APIRouter()


@router.get("/auth/google/authorize")
async def google_authorize(
    request: Request,
    flow: str = "login",
    scopes: list[str] = Query(default=["openid", "email", "profile"]),
) -> JSONResponse:
    """Genera la URL de autorización de Google.

    flow='login'    → si el perfil no tiene cuenta en fit-app, redirige a /login con error.
    flow='register' → si el perfil no tiene cuenta en fit-app, redirige a /register con token.
    """
    csrf_token = secrets.token_urlsafe(32)
    state_data = {
        CSRF_TOKEN_KEY: csrf_token,
        "aud": STATE_TOKEN_AUDIENCE,
        "flow": flow,
    }
    state = jwt.encode(state_data, settings.jwt_secret, algorithm="HS256")
    authorization_url = await google_oauth_client.get_authorization_url(
        BACKEND_CALLBACK_URL,
        state=state,
        scope=scopes,
    )
    response = JSONResponse({"authorization_url": authorization_url})
    response.set_cookie(
        CSRF_TOKEN_COOKIE_NAME,
        csrf_token,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response


@router.get("/auth/google/callback")
async def google_oauth_callback(
    request: Request,
    state: str,
    access_token_state=Depends(_oauth2_callback),
    user_manager=Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
) -> RedirectResponse:
    token, _ = access_token_state

    # Validar CSRF
    try:
        state_data = decode_jwt(state, settings.jwt_secret, [STATE_TOKEN_AUDIENCE])
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="OAUTH_INVALID_STATE")

    csrf_token = state_data.get(CSRF_TOKEN_KEY)
    cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
    if not csrf_token or csrf_token != cookie_csrf:
        raise HTTPException(status_code=400, detail="OAUTH_CSRF_ERROR")

    flow = state_data.get("flow", "login")

    # Obtener datos de la cuenta Google
    try:
        account_id, account_email = await google_oauth_client.get_id_email(
            token["access_token"]
        )
    except (httpx.ReadTimeout, httpx.ConnectError, httpx.HTTPError, Exception):
        qs = urllib.parse.urlencode({"google_error": "Error al conectar con Google. Inténtalo de nuevo."})
        return RedirectResponse(f"{settings.frontend_url}/login?{qs}", status_code=302)

    # Comprobar si ya existe una cuenta en fit-app para este perfil
    user_exists = False

    existing = await user_manager.user_db.get_by_oauth_account(
        google_oauth_client.name, account_id
    )
    if existing is not None:
        user_exists = True
    else:
        try:
            await user_manager.get_by_email(account_email)
            user_exists = True
        except UserNotExists:
            pass

    if not user_exists:
        if flow == "register":
            # Flujo registro: redirigir con token para completar perfil
            from fitapp.services.otp import create_google_registration_token
            try:
                profile = await google_oauth_client.get_profile(token["access_token"])
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.HTTPError, Exception):
                profile = {}
            first_name = profile.get("given_name", "")
            last_name = profile.get("family_name", "")
            reg_token = create_google_registration_token(
                email=account_email,
                first_name=first_name,
                last_name=last_name,
                account_id=account_id,
                google_access_token=token["access_token"],
                expires_at=token.get("expires_at"),
                refresh_token=token.get("refresh_token"),
            )
            qs = urllib.parse.urlencode({
                "google_token": reg_token,
                "first_name": first_name,
                "last_name": last_name,
            })
            return RedirectResponse(f"{settings.frontend_url}/register?{qs}", status_code=302)
        else:
            # Flujo login: no crear cuenta, mostrar error
            qs = urllib.parse.urlencode({
                "google_error": "No tienes cuenta en fit-app con este perfil de Google. Regístrate primero.",
            })
            return RedirectResponse(f"{settings.frontend_url}/login?{qs}", status_code=302)

    # La cuenta existe → asociar OAuth si aún no estaba y hacer login
    try:
        user = await user_manager.oauth_callback(
            oauth_name=google_oauth_client.name,
            access_token=token["access_token"],
            account_id=account_id,
            account_email=account_email,
            expires_at=token.get("expires_at"),
            refresh_token=token.get("refresh_token"),
            request=request,
            associate_by_email=True,
            is_verified_by_default=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="OAUTH_CALLBACK_ERROR") from exc

    if not user.is_active:
        raise HTTPException(status_code=400, detail="LOGIN_USER_NOT_ACTIVE")

    jwt_token = await strategy.write_token(user)
    return RedirectResponse(
        f"{settings.frontend_url}/auth/google/callback?access_token={jwt_token}",
        status_code=302,
    )
