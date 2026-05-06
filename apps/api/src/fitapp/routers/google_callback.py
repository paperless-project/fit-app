"""Callback OAuth2 de Google: intercambia el code por JWT y redirige al frontend."""
from __future__ import annotations

import urllib.parse

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
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

    # Obtener datos de la cuenta Google
    account_id, account_email = await google_oauth_client.get_id_email(
        token["access_token"]
    )

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
        # No hay cuenta → redirigir al registro con mensaje explicativo
        qs = urllib.parse.urlencode({
            "google_error": "No existe una cuenta de fit-app para este perfil de Google.",
        })
        return RedirectResponse(f"{settings.frontend_url}/register?{qs}", status_code=302)

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
