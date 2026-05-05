# Plan de trabajo — fit-app

Aplicación web para leer ficheros FIT (Flexible and Interoperable Data Transfer) de actividades ciclistas y generar visualizaciones (mapas GPS, gráficas, agregados). Los ficheros fuente están en `/workspace/xabi/Activities/` (118 ficheros `.fit`).

## 1. Decisiones de arquitectura

| Decisión | Elección | Motivo |
|---|---|---|
| Dónde se parsea el FIT | Backend (Python `fitparse`) | Una sola fuente de verdad; reprocesable si cambia el esquema |
| Backend | Python + FastAPI + SQLAlchemy 2.0 + Alembic | Ecosistema fuerte para análisis de datos; OpenAPI gratis |
| Base de datos | PostgreSQL 16 + PostGIS | JSONB con índices, geoespacial maduro, particionado nativo |
| Frontend | React + Vite + TypeScript + Tailwind | Ecosistema gráficas/mapas maduro; sin SSR necesario |
| Auth | `fastapi-users` (JWT) | Registro, login, hashing y refresh tokens ya implementados |
| Multi-usuario | Previsto desde el inicio | Tabla `users` y FK `user_id` en `activities` |
| Despliegue dev | Docker Compose (db + api + web) | Reproducible, hot-reload con volúmenes montados |
| Gestor paquetes Python | `uv` | Rápido, moderno, lockfile reproducible |
| Importación inicial | Script CLI `scripts/bulk_import.py` | Más control para los 118 ficheros de partida |

## 2. Stack técnico detallado

### Backend (`apps/api`)
- **FastAPI** + **uvicorn** (ASGI)
- **SQLAlchemy 2.0** (estilo declarativo nuevo) + **Alembic** (migraciones)
- **GeoAlchemy2** + **Shapely** para tipos geoespaciales
- **fitparse** para leer los ficheros `.fit`
- **fastapi-users[sqlalchemy]** para autenticación
- **pydantic-settings** para configuración por entorno
- **pytest** + **pytest-asyncio** + **httpx** para tests

### Frontend (`apps/web`)
- **React 18** + **Vite 5** + **TypeScript 5**
- **Tailwind CSS** + componentes propios (sin librería pesada)
- **TanStack Query** para llamadas a la API y cache cliente
- **React Router** para navegación
- **Chart.js** + `react-chartjs-2` para gráficas (alternativa: Recharts)
- **Leaflet** + `react-leaflet` para mapas (OSM tiles)
- **openapi-typescript** para generar el cliente API desde el OpenAPI de FastAPI
- **Zustand** para estado global ligero

### Infraestructura
- **PostgreSQL 16** con extensión **PostGIS** (imagen `postgis/postgis:16-3.4`)
- **Docker Compose** con `docker-compose.yml` (base) + `docker-compose.override.yml` (dev)
- **Adminer** opcional para inspección de BD

## 3. Estructura del repositorio

```
fit-app/
├── README.md
├── CLAUDE.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docker-compose.override.yml
├── doc/
│   └── PLAN.md
├── apps/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   ├── src/fitapp/
│   │   │   ├── __init__.py
│   │   │   ├── main.py            # app FastAPI
│   │   │   ├── config.py          # pydantic-settings
│   │   │   ├── db.py              # engine + session
│   │   │   ├── models/            # User, Activity, Record, Lap
│   │   │   ├── schemas/           # Pydantic
│   │   │   ├── routers/           # auth, activities, stats
│   │   │   ├── services/          # fit_parser, stats
│   │   │   └── auth/              # config fastapi-users
│   │   └── tests/
│   └── web/
│       ├── Dockerfile
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       ├── postcss.config.js
│       ├── index.html
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── index.css
│           ├── components/
│           ├── pages/
│           ├── hooks/
│           ├── lib/               # api client, formateadores
│           └── types/
└── scripts/
    └── bulk_import.py             # carga inicial de Activities/
```

## 4. Esquema de base de datos

```sql
-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS citext;

-- Usuarios (fastapi-users)
CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  email           citext UNIQUE NOT NULL,
  hashed_password text NOT NULL,
  is_active       boolean NOT NULL DEFAULT true,
  is_superuser    boolean NOT NULL DEFAULT false,
  is_verified     boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Actividades (resumen por salida)
CREATE TABLE activities (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  file_hash       text NOT NULL,
  file_name       text NOT NULL,
  sport           text,
  started_at      timestamptz NOT NULL,
  duration_s      integer,
  moving_time_s   integer,
  distance_m      numeric(10,2),
  ascent_m        numeric(8,2),
  descent_m       numeric(8,2),
  avg_speed_mps   numeric(6,3),
  max_speed_mps   numeric(6,3),
  avg_hr          integer,
  max_hr          integer,
  avg_cadence     integer,
  avg_power       integer,
  calories        integer,
  start_point     geography(Point, 4326),
  bbox            geography(Polygon, 4326),
  summary         jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, file_hash)
);
CREATE INDEX activities_user_started_idx ON activities (user_id, started_at DESC);
CREATE INDEX activities_start_point_gix  ON activities USING GIST (start_point);
CREATE INDEX activities_summary_gin      ON activities USING GIN (summary);

-- Records (serie temporal, ~1 fila por segundo)
CREATE TABLE records (
  activity_id  uuid NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  ts           timestamptz NOT NULL,
  position     geography(Point, 4326),
  altitude_m   numeric(7,2),
  distance_m   numeric(10,2),
  speed_mps    numeric(6,3),
  heart_rate   smallint,
  cadence      smallint,
  power        smallint,
  temperature  smallint,
  PRIMARY KEY (activity_id, ts)
);

-- Vueltas (laps)
CREATE TABLE laps (
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  activity_id   uuid NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
  lap_index     integer NOT NULL,
  start_time    timestamptz NOT NULL,
  duration_s    integer,
  distance_m    numeric(10,2),
  avg_speed_mps numeric(6,3),
  avg_hr        integer,
  ascent_m      numeric(8,2),
  UNIQUE (activity_id, lap_index)
);
```

## 5. API REST

### Autenticación (`fastapi-users`)
- `POST /auth/register`
- `POST /auth/jwt/login`
- `POST /auth/jwt/logout`
- `GET  /users/me`

### Actividades
- `POST   /activities/upload` — multipart, uno o varios `.fit`
- `GET    /activities` — paginado, filtros `from`, `to`, `sport`
- `GET    /activities/{id}`
- `GET    /activities/{id}/records` — serie temporal completa
- `GET    /activities/{id}/laps`
- `DELETE /activities/{id}`

### Estadísticas
- `GET /stats/summary` — totales del usuario
- `GET /stats/calendar?year=YYYY` — datos para heatmap
- `GET /stats/timeline?bucket=month|week`

Todos los endpoints (excepto auth) filtran por `user_id` extraído del JWT.

## 6. Fases de desarrollo

| Fase | Contenido | Estimación |
|---|---|---|
| **0. Setup** | Repo, Docker Compose, FastAPI hello, Vite hello, conexión Postgres, primera migración Alembic con `users` | 1 día |
| **1. Auth** | `fastapi-users` configurado, registro/login operativos, login en frontend, guard de rutas | ½ día |
| **2. Upload + parsing** | Modelos `Activity/Record/Lap`, servicio `fit_parser`, endpoint upload con dedupe por hash, drag-and-drop con barra de progreso | 1½ días |
| **3. Listado de actividades** | Tabla con filtros, paginación, totales | 1 día |
| **4. Detalle de actividad** | Mapa Leaflet, gráficas sincronizadas (altitud, velocidad, FC, cadencia, potencia), tabla de laps | 2 días |
| **5. Análisis agregado** | Calendario heatmap, evolución mensual, distribución FC | 1–2 días |
| **6. Pulido** | Modo oscuro, responsive, exportar PNG, script `bulk_import.py`, README | 1 día |

**Total estimado: 8–10 días.**

## 7. Riesgos / consideraciones

- **Variabilidad entre ficheros FIT:** no todos traen potencia, cadencia o temperatura. La UI debe ocultar gráficas vacías en lugar de mostrarlas planas.
- **Huecos en GPS:** filtrar puntos atípicos antes de pintar la ruta (saltos > umbral).
- **Carga inicial de 118 ficheros:** procesar en lote con barra de progreso; commits por bloques para no agotar memoria.
- **Privacidad de datos GPS:** las actividades pertenecen a un usuario; nunca exponer datos cruzados sin auth.
- **Tamaño de `records`:** una salida de 2h ≈ 7200 filas. 118 actividades ≈ 1M filas. PostgreSQL lo gestiona sin problema con el índice por PK compuesta. Si crece mucho, valorar `TimescaleDB`.

## 8. Estado actual

- Estructura del repo creada
- `CLAUDE.md` con contexto del proyecto
- Ficheros de configuración base (Docker, env, gitignore)
- Esqueletos de `apps/api` y `apps/web`
- Script `scripts/bulk_import.py` (esqueleto)

**Siguiente paso:** Fase 0 — completar `apps/api/main.py` con conexión real a Postgres y crear la primera migración Alembic con la tabla `users`.
