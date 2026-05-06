# DevOps / Docker

## Servicios

| Servicio | Imagen / Build | Puerto host | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | 5432 | healthcheck pg_isready |
| `api` | `./apps/api` | 8000 | uvicorn --reload en dev |
| `web` | `./apps/web` | 5173 | vite dev en dev |
| `adminer` | `adminer:latest` | 8080 | solo docker-compose.override.yml |
| `mailpit` | `axllent/mailpit:latest` | 1026→SMTP, 8026→UI | 1025 del host ocupado → 1026:1025 |

## Volúmenes
- `db_data` — datos PostgreSQL
- `api_venv` → `/opt/venv` — venv Python (**CRÍTICO**: fuera de `/app`, que está montado como bind mount)
- `web_node_modules` → `/app/node_modules`
- `/workspace/xabi/Activities` → `/activities:ro` — ficheros .fit (read-only)

## Variables de entorno api (docker-compose.override.yml)
```
PYTHONPATH=/app/src
SMTP_HOST=mailpit  SMTP_PORT=1025  SMTP_FROM=noreply@fit-app.local
FRONTEND_URL=http://localhost:5173
JWT_SECRET=...  (30 bytes en dev → warning; producción: openssl rand -hex 32)
```

## Comandos habituales
```bash
# Arrancar / rebuild normal
docker compose up --build -d

# Rebuild completo (obligatorio si cambia pyproject.toml o Dockerfile)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Tests
docker compose exec api pytest

# Migraciones
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar el fichero generado antes de aplicar

# Importar .fit en bulk
docker compose exec api python bulk_import.py --user-email EMAIL --path /activities

# Enriquecer nombres post-import (Nominatim, ~15-20 min para 114 actividades)
docker compose exec api python enrich_names.py --all-users
docker compose exec api python enrich_names.py --user-email EMAIL --force
```

## Gotcha crítico venv
El `Dockerfile` instala venv en `/opt/venv`.
`docker-compose.override.yml` monta `./apps/api:/app` (taparía `/app/.venv`).
`api_venv:/opt/venv` preserva el venv entre reinicios.
`PYTHONPATH=/app/src` es imprescindible (uv editable install no genera `.pth`).
