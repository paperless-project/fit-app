"""Configuracion de fastapi-users: backend JWT, manager y dependencias."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, InvalidPasswordException, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.exceptions import GetIdEmailError
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.config import settings
from fitapp.db import get_session
from fitapp.models.user import OAuthAccount, User
from fitapp.services.email import send_verification_email

class _GoogleOAuth2(GoogleOAuth2):
    """Sobreescribe get_id_email para usar el endpoint OpenID estándar en lugar
    de la Google People API (que requiere habilitarla aparte en Cloud Console)."""

    async def get_id_email(self, token: str) -> tuple[str, str | None]:
        async with self.get_httpx_client() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise GetIdEmailError(response=response)
        data = response.json()
        return str(data["id"]), data.get("email")

    async def get_profile(self, token: str) -> dict:
        async with self.get_httpx_client() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            return {}
        return response.json()


google_oauth_client = _GoogleOAuth2(
    settings.google_oauth_client_id,
    settings.google_oauth_client_secret,
)


async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def validate_password(self, password: str, user) -> None:  # type: ignore[override]
        if len(password) < 8:
            raise InvalidPasswordException(reason="REGISTER_INVALID_PASSWORD")

    async def on_after_register(self, user: User, request=None) -> None:
        # Los usuarios OAuth llegan con is_verified=True; no enviarles verificación
        if not user.is_verified:
            await self.request_verify(user, request)

    async def on_after_request_verify(self, user: User, token: str, request=None) -> None:
        await send_verification_email(user.email, token)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
bearer_transport_remember = BearerTransport(tokenUrl="auth/jwt-remember/login")

_REMEMBER_ME_LIFETIME = 15 * 24 * 3600  # 15 días en segundos


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


def get_jwt_strategy_remember() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=_REMEMBER_ME_LIFETIME)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

auth_backend_remember = AuthenticationBackend(
    name="jwt-remember",
    transport=bearer_transport_remember,
    get_strategy=get_jwt_strategy_remember,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend, auth_backend_remember]
)

current_active_user = fastapi_users.current_user(active=True)
