# DevOps / Docker

## Servicios

| Servicio | Imagen / Build | Puerto host | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | 5432 | healthcheck pg_isready |
| `api` | `./apps/api` | 8000 | uvicorn --reload; watchfiles detecta cambios |
| `web` | `./apps/web` | 5173 | vite dev |
| `adminer` | `adminer:latest` | 8080 | docker-compose.override.yml |
| `mailpit` | `axllent/mailpit` | 1026→SMTP, 8026→UI | puerto 1025 host ocupado → mapear 1026:1025 |

## Variables de entorno (docker-compose.yml — bloque api.environment)
```
POSTGRES_USER/PASSWORD/DB/HOST/PORT
JWT_SECRET                      256 bits (openssl rand -hex 32); lifetime: 28800s (8h)
JWT_LIFETIME_SECONDS
CORS_ORIGINS
ACTIVITIES_DIR=/activities
GOOGLE_OAUTH_CLIENT_ID/SECRET   para login/registro con Google
STRAVA_CLIENT_ID/SECRET         para importar actividades desde Strava
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
PYTHONPATH=/app/src             imprescindible (uv editable no genera .pth)
```
⚠️ **Cada nueva variable de entorno debe añadirse en `docker-compose.yml` Y en `.env.example`.**

## Volúmenes
- `db_data` — datos PostgreSQL
- `api_venv` → `/opt/venv` — venv Python fuera de `/app` (bind mount taparía `/app/.venv`)
- `/workspace/xabi/Activities` → `/activities:ro` — ficheros .fit originales (read-only)

## Comandos habituales
```bash
# Arrancar
docker compose up --build -d

# Rebuild completo (cambios en pyproject.toml o Dockerfile)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Reiniciar solo api (cambios en docker-compose.yml o .env)
docker compose up -d api

# Tests
docker compose exec api pytest
docker compose exec api pytest tests/test_strava.py -v

# Migraciones
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar el fichero: eliminar drop_index de índices GiST antes de aplicar
docker compose exec api alembic upgrade head

# Importar .fit en bulk
docker compose exec api python bulk_import.py --user-email EMAIL --path /activities

# Enriquecer nombres (Nominatim, ~15-20 min para 114 actividades)
docker compose exec api python enrich_names.py --all-users
docker compose exec api python enrich_names.py --user-email EMAIL --force

# httpx-oauth (requiere reinstalación manual tras rebuild por caché Docker)
docker compose exec api uv pip install --python /opt/venv "httpx-oauth>=0.15"
```

## URLs locales
| Servicio | URL |
|---|---|
| API | http://localhost:8000 |
| Docs OpenAPI | http://localhost:8000/docs |
| Web | http://localhost:5173 |
| Adminer | http://localhost:8080 |
| Mailpit | http://localhost:8026 |

## Gotcha venv
El `Dockerfile` instala venv en `/opt/venv`. El bind mount `./apps/api:/app` taparía `/app/.venv`.
`api_venv:/opt/venv` preserva el venv entre reinicios sin mezclar con el código fuente.

## Gotcha uvicorn --reload
`uvicorn --reload` usa watchfiles para detectar cambios. Al guardar un fichero Python:
1. Uvicorn señaliza shutdown
2. **Espera a que terminen los `BackgroundTasks` en curso** (importante si hay un import de Strava activo)
3. Reinicia con el nuevo código

Si hay un background task con sleeps largos (ej. retry 429 de Strava), el reload queda bloqueado hasta que el task termine. Mantener los `asyncio.sleep()` de retry cortos (≤15 s).
