# DevOps / Docker

## Servicios

| Servicio | Imagen / Build | Puerto host | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | 5432 | healthcheck pg_isready |
| `api` | `./apps/api` | 8000 | uvicorn --reload en dev |
| `web` | `./apps/web` | 5173 | vite dev en dev |
| `adminer` | `adminer:latest` | 8080 | solo override dev |
| `mailpit` | `axllent/mailpit:latest` | 1026(SMTP) 8026(UI) | 1025 del host ocupado → mapear 1026:1025 |

## Volúmenes
- `db_data` — datos PostgreSQL
- `api_venv` → `/opt/venv` — venv Python (CRÍTICO: fuera de `/app`, que está montado)
- `web_node_modules` → `/app/node_modules`
- `/workspace/xabi/Activities` → `/activities:ro` — ficheros .fit (read-only)

## Variables de entorno api (docker-compose.override.yml)
```
SMTP_HOST=mailpit  SMTP_PORT=1025  SMTP_FROM=noreply@fit-app.local
FRONTEND_URL=http://localhost:5173
```

## Comandos habituales
```bash
# Arrancar / rebuild
docker compose up --build -d

# Rebuild completo (obligatorio si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Migraciones
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Tests
docker compose exec api pytest

# Bulk import (EJECUTAR DENTRO del contenedor con PYTHONPATH)
# ⚠️ scripts/ NO está en el volumen /app — copiar al contenedor o añadir al Dockerfile
docker compose cp scripts/bulk_import.py api:/app/bulk_import.py
docker compose exec api bash -c "cd /app && PYTHONPATH=/app/src python bulk_import.py --user-email EMAIL --path /activities"
```

## Gotcha crítico venv
El `Dockerfile` instala venv en `/opt/venv`.
`docker-compose.override.yml` monta `./apps/api:/app` (taparía `/app/.venv`).
`api_venv:/opt/venv` preserva el venv entre reinicios.
`PYTHONPATH=/app/src` es imprescindible (uv editable install no genera `.pth`).

## JWT_SECRET
- En dev: 30 bytes → InsecureKeyLengthWarning (inofensivo en dev)
- En producción: usar `openssl rand -hex 32` y configurar en `.env`
