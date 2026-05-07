"""Aplicacion FastAPI: monta routers de auth, actividades y estadisticas."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fitapp import __version__
from fitapp.auth.users import auth_backend, auth_backend_remember, fastapi_users, google_oauth_client
from fitapp.config import settings
from fitapp.routers import account, activities, google_callback, register, stats, strava
from fitapp.schemas import UserCreate, UserRead, UserUpdate

app = FastAPI(title="fit-app API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


# Registro multi-paso (antes de fastapi-users para que /auth/register/* tenga prioridad)
app.include_router(register.router)

# Auth (fastapi-users)
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_auth_router(auth_backend_remember), prefix="/auth/jwt-remember", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"]
)
# Callback personalizado: registrado ANTES del router de fastapi-users para
# que tome precedencia sobre /auth/google/callback y redirija al frontend con el JWT.
app.include_router(google_callback.router, tags=["auth"])
app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        settings.jwt_secret,
        redirect_url=f"{settings.api_url}/auth/google/callback",
        is_verified_by_default=True,
        csrf_token_cookie_secure=False,   # HTTP en desarrollo
    ),
    prefix="/auth/google",
    tags=["auth"],
)
# Cuenta de usuario (antes del router de fastapi-users para que /me literal
# tenga prioridad sobre /{id} parametrizado)
app.include_router(account.router)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

# Recursos de la app
app.include_router(strava.router)
app.include_router(activities.router)
app.include_router(stats.router)
