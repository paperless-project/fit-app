# fit-app — Contexto del proyecto

Aplicación web para leer ficheros FIT (Flexible and Interoperable Data Transfer) de actividades ciclistas, almacenarlos en una base de datos y generar visualizaciones (mapas GPS, gráficas, agregados).

Los ficheros fuente están en `/workspace/xabi/Activities/` (118 ficheros `.fit`, fechados desde julio 2024). Ese directorio es **solo lectura** — no modificar los originales.

## Stack acordado

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2, parsing con `fitparse`
- **Auth:** `fastapi-users` (JWT, multi-usuario desde el inicio)
- **BD:** PostgreSQL 16 + PostGIS (imagen `postgis/postgis:16-3.4`)
- **Frontend:** React 18 + Vite + TypeScript + Tailwind, Chart.js, Leaflet, TanStack Query
- **Infra dev:** Docker Compose (`db` + `api` + `web`) con hot-reload por volúmenes
- **Gestor paquetes Python:** `uv`
- **Gestor paquetes JS:** `pnpm`

## Estructura del repo

```
fit-app/
├── doc/PLAN.md             # plan completo, fases, esquema BD, endpoints
├── docker-compose.yml      # servicios base
├── docker-compose.override.yml  # ajustes dev (volúmenes, hot-reload)
├── apps/
│   ├── api/                # backend Python/FastAPI
│   └── web/                # frontend React/Vite
└── scripts/bulk_import.py  # importación inicial de Activities/
```

## Convenciones

- **Idioma de comunicación con el usuario:** español.
- **Idioma del código y comentarios:** inglés (nombres de variables, funciones, mensajes de log, commits). Docstrings y docs de usuario en `doc/` pueden ir en español.
- **Comentarios:** mínimos. Solo cuando el *por qué* no sea obvio. No describir el *qué* — los nombres ya lo hacen.
- **Migraciones:** siempre vía Alembic (`alembic revision --autogenerate`). Nunca `Base.metadata.create_all()` en producción.
- **Multi-tenant:** todo recurso lleva `user_id` y los endpoints filtran por el usuario del JWT. Nunca exponer datos cruzados.
- **Tests:** `pytest` en backend, Vitest en frontend. Tests de integración del backend hablan con un Postgres real (en Docker), no con SQLite ni mocks de la BD.
- **Tipado:** TypeScript estricto en frontend; type hints completos en backend.

## Comandos habituales

> Estos comandos asumen que estás en la raíz del repo.

### Arrancar todo el stack en dev
```bash
docker compose up --build
```
- API: http://localhost:8000 (docs en `/docs`)
- Web: http://localhost:5173
- DB: `localhost:5432` (`fitapp` / `fitapp` / db `fitapp`)

### Backend
```bash
# Entrar en el contenedor
docker compose exec api bash

# Crear nueva migración (tras tocar models)
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones
docker compose exec api alembic upgrade head

# Tests
docker compose exec api pytest

# Importación inicial de la carpeta Activities
docker compose exec api python -m scripts.bulk_import \
  --user-email javier.fernandez@xercode.es \
  --path /activities
```

### Frontend
```bash
docker compose exec web pnpm install
docker compose exec web pnpm run lint
docker compose exec web pnpm run build
```

### Generar cliente TS desde el OpenAPI del backend
```bash
docker compose exec web pnpm run gen:api
```

## Estado del proyecto

- Estructura del repo creada (esqueleto)
- Plan documentado en `doc/PLAN.md`
- **Siguiente paso:** completar Fase 0 (conexión real a Postgres + primera migración con tabla `users`)

## Decisiones registradas (no preguntar de nuevo)

- Parsing FIT en backend, no en cliente.
- BD relacional: PostgreSQL (no MySQL ni SQLite).
- Auth: `fastapi-users`, no implementación manual de JWT.
- Importación masiva de los 118 ficheros: por CLI, no por UI.
- Carpeta `/workspace/xabi/Activities` se monta read-only en el contenedor api como `/activities`.

## Punteros útiles

- Plan completo: `doc/PLAN.md`
- Especificación FIT: https://developer.garmin.com/fit/
- Librería de parsing: https://github.com/dtcooper/python-fitparse
- `fastapi-users` docs: https://fastapi-users.github.io/fastapi-users/
