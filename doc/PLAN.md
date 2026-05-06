# Plan de trabajo — fit-app

Aplicación web para importar ficheros FIT (actividades ciclistas) y generar visualizaciones (mapas GPS, gráficas, estadísticas). Ficheros fuente: `/workspace/xabi/Activities/` (118 ficheros, 114 `.fit`).

## 1. Decisiones de arquitectura

| Decisión | Elección | Motivo |
|---|---|---|
| Parsing FIT | Backend (Python `fitparse`) | Una sola fuente de verdad; reprocesable |
| Backend | FastAPI + SQLAlchemy 2.0 + Alembic | OpenAPI gratis, async nativo |
| Base de datos | PostgreSQL 16 + PostGIS | Geoespacial maduro; geography nativa |
| Frontend | React 18 + Vite + TypeScript + Tailwind | Ecosistema gráficas/mapas maduro |
| Auth | `fastapi-users` (JWT + verificación email) | Registro, hashing, tokens ya implementados |
| Multi-usuario | Desde el inicio | FK `user_id` en todas las tablas de datos |
| Geocoding | Nominatim OSM (sin API key) | Gratuito, sin límite de cuota estricto |
| Despliegue dev | Docker Compose | Reproducible, hot-reload con volúmenes |
| Gestores de paquetes | `uv` (Python) + `pnpm` (JS) | Rápidos, lockfile reproducible |
| Importación inicial | CLI `bulk_import.py` | Control total sobre 114 ficheros de partida |

## 2. Esquema de base de datos

```sql
-- Extensiones (primera migración)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS citext;

-- Usuarios (gestionado por fastapi-users)
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
  name            varchar(255),          -- geocoding inverso (asíncrono post-upload)
  notes           text,                  -- notas libres del usuario
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
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, file_hash)
);

-- Records (serie temporal, ~1 fila/segundo)
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

-- Vueltas
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

**Migraciones aplicadas:**
- `379c3241c147` — initial_schema (tablas + extensiones + índices GiST)
- `6bf7f63a1065` — add_activity_name
- `472807ab1cee` — add_notes_to_activities

## 3. API REST implementada

```
# Auth
POST /auth/register, /auth/jwt/login, /auth/jwt/logout, /auth/verify
GET|PATCH /users/me

# Cuenta de usuario
PATCH  /users/me/password         cambio de contraseña; 400 si actual errónea; 422 si nueva < 8 chars
DELETE /users/me                  borrado de cuenta con {confirm:true}; cascade activities

# Actividades
GET    /activities/               paginado {items,total,page,size,pages}; filtros: q,sport,date_from,date_to,page,size
GET    /activities/sports         lista deportes distintos del usuario
POST   /activities/upload         multipart .fit → 201; 409 duplicado; 400 inválido
POST   /activities/enrich-names   encola geocoding para actividades con name IS NULL
GET    /activities/export/csv     CSV con mismos filtros (sin paginación, exporta todo)
GET    /activities/{id}           detalle + records + laps
PATCH  /activities/{id}           edición parcial: name, sport, notes
DELETE /activities/{id}           borrado; 403 si no es propietario; 404 si no existe
GET    /activities/{id}/export/gpx  GPX 1.1 con extensiones Garmin

# Estadísticas
GET /stats/summary
GET /stats/calendar?year=YYYY
GET /stats/timeline?bucket=month|year
```

## 4. Fases de desarrollo

| Fase | Contenido | Estado |
|---|---|---|
| **1. Auth** | fastapi-users, JWT, verificación email, frontend auth | ✅ Completa |
| **2. Upload + parsing** | parse_fit, fit_repair, POST /upload, bulk_import CLI | ✅ Completa |
| **3. Listado + nombres** | GET /activities/, geocoding Nominatim, ActivitiesPage | ✅ Completa |
| **4. Detalle** | GET /activities/{id}, mapa Leaflet, gráficas Chart.js sincronizadas | ✅ Completa |
| **5. Estadísticas** | /stats/summary+calendar+timeline, StatsPage, heatmap | ✅ Completa |
| **6. Filtros + edición + exportación** | filtros, PATCH, CSV, GPX | ✅ Completa |
| **7. Enriquecimiento asíncrono** | BackgroundTasks geocoding, CLI enrich_names.py | ✅ Completa |
| **Mejoras** | JWT 256 bits / 8 h, paginación GET /activities/, GET /activities/sports | ✅ Completa |
| **8. Gestión de cuenta** | PATCH /users/me/password, DELETE /users/me, DELETE /activities/{id}, AccountPage | ✅ Completa |

**131 tests pasando.** Ver estado detallado en [`.agent/context/status.md`](../.agent/context/status.md).

## 5. Flujo de datos principal

```
.fit file → POST /activities/upload
          → parse_fit_safe()    # intenta parsear; si falla, repara CRC y reintenta
          → persist_activity()  # dedupe por (user_id, file_hash), INSERT, COMMIT
          → BackgroundTasks: _enrich_name_bg(activity.id)
              → generate_activity_name(records)
                  # Nominatim: start locality + end locality + 5 waypoints intermedios
                  # "POI1, POI2 desde Locality" | "De A a B vía POI"
              → UPDATE activities.name

GET /activities/{id}
          → SELECT activity + ST_AsGeoJSON(records.position) + laps
          → ActivityDetailOut
```

## 6. Consideraciones técnicas

- **Variabilidad FIT:** no todos traen potencia, cadencia o temperatura. La UI oculta gráficas vacías.
- **GPS duplicado:** algunos Garmin repiten el mismo timestamp → deduplicar por `ts` antes de INSERT.
- **geography vs geometry:** usar `ST_AsGeoJSON` para extraer lat/lon (ST_X/ST_Y no aceptan `geography`).
- **Alembic + GiST:** el autogenerate detecta falsos positivos con índices GiST → revisar siempre el fichero generado.
- **Geocoding rate-limit:** Nominatim permite máx 1 req/s → enriquecimiento de 114 actividades tarda ~15-20 min.
- **Tamaño records:** ~1 fila/segundo × 114 actividades ≈ cientos de miles de filas. PK compuesta `(activity_id, ts)` es suficiente para el volumen actual.
