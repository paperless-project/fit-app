# DevOps / Docker

## Servicios

| Servicio | Imagen / Build | Puerto host | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | 5432 | healthcheck pg_isready |
| `api` | `./apps/api` | 8000 | uvicorn --reload en dev |
| `web` | `./apps/web` | 5173 | vite dev en dev |
| `adminer` | `adminer:latest` | 8080 | solo override dev |
| `mailpit` | `axllent/mailpit:latest` | 1026 (SMTP), 8026 (UI) | solo override dev; 1025 del host ocupado |

## Variables de entorno de api (docker-compose.override.yml)
```
SMTP_HOST=mailpit       # nombre del servicio Docker
SMTP_PORT=1025          # puerto interno del contenedor mailpit
SMTP_FROM=noreply@fit-app.local
FRONTEND_URL=http://localhost:5173
```

## Volúmenes
- `db_data` — datos PostgreSQL
- `api_venv` → `/opt/venv` — venv Python (CRÍTICO: fuera de `/app`)
- `web_node_modules` → `/app/node_modules`
- `/workspace/xabi/Activities` → `/activities:ro` — ficheros .fit (read-only)

## Gotcha crítico del venv
El `Dockerfile` instala el venv en `/opt/venv`.  
`docker-compose.override.yml` monta `./apps/api:/app` y `api_venv:/opt/venv`.  
`PYTHONPATH=/app/src` en `docker-compose.yml` es imprescindible.

## Comandos

```bash
# Arrancar / reconstruir
docker compose up --build -d

# Rebuild completo (obligatorio si cambia pyproject.toml)
docker compose down
docker volume rm fit-app_api_venv
docker compose up --build -d

# Migraciones
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Tests
docker compose exec api pytest

# Logs
docker compose logs -f api
docker compose logs -f mailpit
```

## Variables de entorno
Copiar `.env.example` → `.env`. Nunca commitear `.env`.  
`JWT_SECRET` — cambiar en cualquier deploy no-local (actualmente 30 bytes, avisa warning; usar ≥32).
