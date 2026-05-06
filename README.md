# fit-app

Aplicación web para importar ficheros FIT (actividades ciclistas), almacenarlos en PostgreSQL+PostGIS y generar visualizaciones: mapa GPS, gráficas de altitud/velocidad/FC/cadencia/potencia, estadísticas agregadas y calendario de actividad. Multi-usuario con autenticación JWT.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + verificación email) |
| Parsing FIT | `fitparse` + reparación CRC-16 propia |
| Geocoding | Nominatim OSM (sin API key) |
| BD | PostgreSQL 16 + PostGIS |
| Frontend | React 18 + Vite + TypeScript + Tailwind + Chart.js + Leaflet |
| Infra dev | Docker Compose |

## Requisitos

- Docker Engine + Docker Compose v2

No es necesario tener Python ni Node instalados localmente.

## Arranque rápido

```bash
# 1. Variables de entorno
cp .env.example .env

# 2. Levantar el stack completo
docker compose up --build -d

# 3. Aplicar migraciones
docker compose exec api alembic upgrade head
```

## URLs locales

| Servicio | URL | Notas |
|---|---|---|
| Web | http://localhost:5173 | UI principal |
| API | http://localhost:8000 | REST + `/docs` OpenAPI |
| Adminer | http://localhost:8080 | Inspección BD (system: PostgreSQL, server: db) |
| Mailpit | http://localhost:8026 | Bandeja de entrada emails dev |
| DB | localhost:5432 | usuario/contraseña: `fitapp` |

## Importar actividades

```bash
# 1. Registrar un usuario (desde la UI o la consola)
# 2. Importar los ficheros .fit en bulk
docker compose exec api python bulk_import.py --user-email tu@email.com --path /activities

# 3. Enriquecer los nombres via geocoding inverso (Nominatim, ~1 min por actividad)
docker compose exec api python enrich_names.py --user-email tu@email.com
# O para todos los usuarios:
docker compose exec api python enrich_names.py --all-users
```

`/activities` está montado en el contenedor desde `/workspace/xabi/Activities` en modo solo-lectura.

## Tests

```bash
docker compose exec api pytest
# → 131 tests pasando
```

## Desarrollo

```bash
# Nueva migración tras modificar models/
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar el fichero antes de aplicar: autogenerate detecta falsos positivos con índices GiST
docker compose exec api alembic upgrade head

# Rebuild completo (si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d
```

## Estructura del repositorio

```
fit-app/
├── CLAUDE.md                    Contexto técnico y convenciones para sesiones de IA
├── doc/PLAN.md                  Plan de desarrollo y decisiones de arquitectura
├── .agent/context/              Documentación técnica detallada por área
│   ├── api.md                   Endpoints, schemas, servicios, tests
│   ├── architecture.md          Flujos de datos, decisiones irreversibles
│   ├── database.md              Esquema BD, migraciones, gotchas
│   ├── devops.md                Docker, comandos, variables de entorno
│   ├── frontend.md              Estructura React, componentes, convenciones
│   └── status.md                Estado de fases y trabajo pendiente
├── apps/api/                    Backend FastAPI
│   ├── src/fitapp/
│   │   ├── routers/             activities.py, stats.py
│   │   ├── services/            fit_parser.py, fit_repair.py, geocoding.py, activity_service.py
│   │   ├── models/              activity.py, user.py
│   │   └── schemas/             activity.py, stats.py
│   ├── alembic/versions/        Migraciones Alembic
│   ├── tests/                   Suite pytest (119 tests)
│   ├── scripts/bulk_import.py   CLI importación masiva de .fit
│   └── enrich_names.py          CLI geocoding inverso de nombres
└── apps/web/                    Frontend React + Vite
    └── src/
        ├── pages/               ActivitiesPage, ActivityDetailPage, StatsPage, AccountPage, Auth*
        ├── components/          ActivityMap, ActivityCharts, Layout
        └── lib/                 activities.ts, stats.ts, account.ts, api.ts
```

## Funcionalidades implementadas

- **Auth**: registro, verificación email, login/logout JWT (8 h), perfil
- **Upload**: drag-and-drop `.fit`, deduplicación por hash, reparación automática de ficheros corruptos
- **Listado**: paginado (20/página), filtros por nombre/deporte/fecha, exportar CSV completo
- **Detalle**: mapa Leaflet con traza GPS, gráficas Chart.js sincronizadas (altitud, velocidad, FC, cadencia, potencia), tabla de vueltas, exportar GPX
- **Edición**: nombre, deporte y notas de cada actividad; borrado individual con confirmación
- **Nombres automáticos**: geocoding inverso Nominatim asíncrono — genera nombres tipo "Castillo de Olite desde Tafalla"
- **Estadísticas**: totales, calendario heatmap estilo GitHub, evolución mensual
- **Gestión de cuenta** (`/account`): cambio de contraseña, borrado de cuenta con cascada de actividades

Contexto técnico completo en [`CLAUDE.md`](CLAUDE.md) y [`doc/PLAN.md`](doc/PLAN.md).
