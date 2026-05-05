# DevOps / Docker

## Servicios
| Servicio | Imagen / Build | Puerto | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | 5432 | healthcheck pg_isready |
| `api` | `./apps/api` | 8000 | uvicorn --reload en dev |
| `web` | `./apps/web` | 5173 | vite dev en dev |
| `adminer` | `adminer:latest` | 8080 | solo en override dev |

## Volúmenes
- `db_data` — datos PostgreSQL
- `api_venv` → `/opt/venv` — venv Python (fuera de `/app` para no ser sobreescrito por volumen de código)
- `web_node_modules` → `/app/node_modules`
- `/workspace/xabi/Activities` → `/activities:ro` — ficheros .fit originales (read-only)

## Gotcha crítico del venv
El `Dockerfile` del api instala el venv en `/opt/venv` (no `/app/.venv`).  
El `docker-compose.override.yml` monta `./apps/api:/app` y `api_venv:/opt/venv`.  
`PYTHONPATH=/app/src` en `docker-compose.yml` es imprescindible — sin él el módulo `fitapp` no se encuentra porque el install editable con uv no crea `.pth` en la primera build.

## Rebuild total
```bash
docker compose down
docker volume rm fit-app_api_venv  # necesario si cambia pyproject.toml
docker compose up --build -d
docker compose exec api alembic upgrade head
```

## Solo reiniciar api (cambios en código, sin dependencias nuevas)
```bash
docker compose restart api   # o simplemente guardar un .py (hot-reload)
```

## Añadir dependencia Python
```bash
# 1. Editar apps/api/pyproject.toml
# 2. Rebuild imagen (recrea el venv)
docker compose up --build -d api
```

## Variables de entorno
Copiar `.env.example` → `.env`. Nunca commitear `.env` (está en .gitignore).  
Clave `JWT_SECRET` — cambiar en cualquier deploy no-local.
