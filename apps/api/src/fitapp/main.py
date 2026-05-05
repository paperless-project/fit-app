"""Aplicacion FastAPI: monta routers de auth, actividades y estadisticas."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fitapp import __version__
from fitapp.auth.users import auth_backend, fastapi_users
from fitapp.config import settings
from fitapp.routers import activities, stats
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


# Auth (fastapi-users)
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

# Recursos de la app
app.include_router(activities.router)
app.include_router(stats.router)
