"""Configuracion de la aplicacion (variables de entorno)."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "fitapp"
    postgres_password: str = "fitapp"
    postgres_db: str = "fitapp"
    postgres_host: str = "db"
    postgres_port: int = 5432

    jwt_secret: str = Field(default="change-me", min_length=8)
    jwt_lifetime_seconds: int = 3600

    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@fit-app.local"
    smtp_starttls: bool = False

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    strava_client_id: str = ""
    strava_client_secret: str = ""
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    cors_origins: str = "http://localhost:5173"
    activities_dir: str = "/activities"

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
