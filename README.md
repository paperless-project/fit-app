# fit-app

Aplicación web para leer ficheros FIT (Flexible and Interoperable Data Transfer) de actividades ciclistas, almacenarlos en PostgreSQL y generar visualizaciones: mapa GPS de la ruta, gráficas de altitud / velocidad / frecuencia cardíaca / cadencia / potencia, y agregados (totales, calendario, evolución).

## Arquitectura

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2
- **Parsing:** `fitparse` (en el backend, una sola fuente de verdad)
- **Auth:** `fastapi-users` con JWT (multi-usuario)
- **BD:** PostgreSQL 16 + PostGIS
- **Frontend:** React 18 + Vite + TypeScript + Tailwind + Chart.js + Leaflet
- **Infra dev:** Docker Compose

Plan completo en [`doc/PLAN.md`](doc/PLAN.md). Contexto y convenciones para futuras sesiones de desarrollo en [`CLAUDE.md`](CLAUDE.md).

## Requisitos

- Docker Desktop / Docker Engine
- Docker Compose v2

No es necesario tener Python ni Node instalados localmente: todo corre en contenedores.

## Arranque rápido

```bash
# 1. Copiar variables de entorno
cp .env.example .env

# 2. Levantar todo (db + api + web + adminer)
docker compose up --build

# 3. Aplicar migraciones (en otra terminal)
docker compose exec api alembic upgrade head
```

Servicios:

| Servicio | URL                       | Notas                              |
|----------|---------------------------|------------------------------------|
| Web      | http://localhost:5173     | UI                                 |
| API      | http://localhost:8000     | Docs en `/docs`, OpenAPI en `/openapi.json` |
| Adminer  | http://localhost:8080     | Inspección de la BD (system: PostgreSQL, server: db) |
| DB       | localhost:5432            | usuario/contraseña `fitapp` por defecto |

## Importar la carpeta `Activities/` por primera vez

```bash
# Crear primero un usuario con POST /auth/register desde la UI o curl
docker compose exec api python -m scripts.bulk_import \
  --user-email tu@email.com \
  --path /activities
```

`/activities` está montado en el contenedor desde `/workspace/xabi/Activities` en modo solo-lectura.

## Desarrollo

```bash
# Backend: nueva migración tras tocar models
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head

# Tests backend
docker compose exec api pytest

# Frontend: regenerar cliente TS desde el OpenAPI del backend
docker compose exec web pnpm run gen:api
```

## Estructura del repositorio

```
fit-app/
├── doc/PLAN.md         Plan completo del proyecto
├── CLAUDE.md           Contexto y convenciones para sesiones de IA
├── docker-compose.yml  Servicios base
├── docker-compose.override.yml  Ajustes para dev
├── apps/api/           Backend FastAPI
├── apps/web/           Frontend React + Vite
└── scripts/            Utilidades CLI (importación masiva)
```

## Estado

Esqueleto inicial creado. Próximo hito: completar la Fase 0 — primera migración Alembic y verificación del stack en local. Ver [`doc/PLAN.md`](doc/PLAN.md) §6.
