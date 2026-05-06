# fit-app — Memoria del proyecto

## Objetivo
App web para importar ficheros FIT (actividades ciclistas), almacenarlos en PostgreSQL+PostGIS y generar visualizaciones: mapa GPS, gráficas, estadísticas. Multi-usuario con auth JWT.

Ficheros fuente: `/workspace/xabi/Activities/` (118 ficheros, 114 `.fit`) → montados en `/activities:ro`. **No modificar.**

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + verificación email) |
| Email dev | Mailpit (SMTP local, puerto 1026:1025) |
| Parsing FIT | `fitparse` + `services/fit_repair.py` (CRC-16 + trim progresivo) |
| Geocoding | `services/geocoding.py` (Nominatim OSM, 1 req/s, caché ~1km) |
| BD | PostgreSQL 16 + PostGIS (`postgis/postgis:16-3.4`) |
| Frontend | React 18 + Vite + TypeScript + Tailwind + Chart.js + Leaflet + TanStack Query + Zustand |
| Infra dev | Docker Compose (`db`, `api`, `web`, `adminer`, `mailpit`) |
| Paquetes Python | `uv` (venv en `/opt/venv`, fuera del volumen `/app`) |
| Paquetes JS | `pnpm` |

---

## Decisiones clave (no preguntar de nuevo)
- Parsing en **backend**, no en cliente
- BD: **PostgreSQL** (no MySQL ni SQLite)
- Auth: **`fastapi-users`**, no JWT manual
- Import masivo: **CLI** (`apps/api/bulk_import.py`), no UI
- Multi-usuario desde el inicio: `user_id FK` en `activities`
- **Una fase no se da por completada hasta que todos los tests pasen al 100%**

---

## Gotchas técnicos críticos

- **Venv en `/opt/venv`** — el volumen dev monta `/app`, taparía `/app/.venv`
- **`PYTHONPATH=/app/src`** — uv editable install no crea `.pth` correctamente
- **`spatial_index=False`** en todos los `Geography(...)` — GeoAlchemy2 crea índices que colisionan con Alembic
- **`include_object` en `alembic/env.py`** — filtra ~35 tablas PostGIS/Tiger del autogenerate
- **Alembic autogenerate detecta falsos positivos de índices GiST** — revisar siempre el fichero antes de aplicar
- Nunca `Base.metadata.create_all()` — siempre Alembic
- Extensiones (`uuid-ossp`, `postgis`, `citext`) se crean en la primera migración
- **Tests usan `NullPool`** — sin reutilización de conexiones entre tests
- **`ST_X`/`ST_Y` no funcionan sobre `geography`** — usar `ST_AsGeoJSON` + `json.loads()`
- **Timestamps duplicados en records Garmin** — deduplicar por `ts` antes de insertar (ya corregido)
- **Mock de email**: `patch("fitapp.auth.users.send_verification_email")`
- **Mock de geocoding**: `patch("fitapp.services.activity_service.generate_activity_name")`
- **Mock de background task enrich**: `patch("fitapp.routers.activities._enrich_name_bg")` — parchear donde se USA (el router), no donde está definida
- Puerto 1025 del host ocupado → Mailpit usa `1026:1025`

---

## Estado actual (2026-05-06) — Fase 7 + paginación — 119 tests

### Fase 1 ✅ — Auth
Register + verify email + login/logout + `/users/me`. Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore (Zustand).

### Fase 2 ✅ — Parser FIT + Upload
- `parse_fit()` + `parse_fit_safe()` + `fit_repair.py` (CRC-16 + trim)
- `POST /activities/upload`: multipart, dedupe `(user_id, file_hash)`, 409/400
- `GET /activities/`: lista autenticada
- `bulk_import.py`: 114/114 importados

### Fase 3 ✅ — Listado frontend + nombres
- `geocoding.py`: Nominatim, caché dict, rate-limit 1.1s
- Columna `name` en `activities` (migración `6bf7f63a1065`)
- `ActivitiesPage`: tabla, modal upload drag-and-drop, filas clicables

### Fase 4 ✅ — Detalle de actividad
- `GET /activities/{id}`: activity + records (via ST_AsGeoJSON) + laps
- `ActivityDetailPage`: stats, mapa Leaflet, gráficas Chart.js sincronizadas, tabla vueltas

### Fase 5 ✅ — Dashboard estadísticas
- `GET /stats/summary`: km, horas, actividades, desnivel totales
- `GET /stats/calendar?year=YYYY`: datos heatmap por día
- `GET /stats/timeline?bucket=month|year`: evolución mensual/anual
- `StatsPage`: tarjetas, heatmap estilo GitHub, gráfica de barras mensual

### Fase 6 ✅ — Filtros, edición, exportación
- Filtros en `GET /activities/`: `q`, `sport`, `date_from`, `date_to`
- `PATCH /activities/{id}`: edición parcial `name`/`sport`/`notes` (migración `472807ab1cee`)
- `GET /activities/export/csv`: exporta lista filtrada
- `GET /activities/{id}/export/gpx`: genera GPX 1.1 con extensiones Garmin
- Frontend: FilterBar, botón CSV, EditModal, botón GPX

### Fase 7 ✅ — Enriquecimiento asíncrono de nombres
- `geocoding.py` mejorado: haversine bucle/p2p, start + end locality (zoom 13) + 5 waypoints (zoom 17, fracs 0.15/0.30/0.50/0.70/0.85), máx 3 POIs
- `enrich_activity_name(db, id, force=False)`: carga records BD → geocoding → actualiza name
- `_enrich_name_bg(id)`: tarea de fondo con sesión propia, encola tras cada upload
- `persist_activity()`: ya no bloquea con geocoding; respuesta inmediata
- `POST /activities/enrich-names`: encola todas las actividades con `name IS NULL` del usuario
- `apps/api/enrich_names.py` (CLI): `python enrich_names.py --user-email EMAIL [--force]` o `--all-users`

### Mejoras adicionales ✅
- **JWT_SECRET**: 256 bits (64 hex), generado con `openssl rand -hex 32`; lifetime 8 h (`JWT_LIFETIME_SECONDS=28800`)
- **Paginación**: `GET /activities/` devuelve `{items, total, page, size, pages}`; `?page=1&size=20` (máx 100). `GET /activities/sports` para deportes distintos del usuario. Frontend: componente `Pagination` con prev/next y numeración.

---

## Bugs conocidos / trabajo pendiente
- Las 114 actividades importadas en bulk tienen `name IS NULL` → ejecutar `docker compose exec api python enrich_names.py --all-users` (tarda ~15-20 min por rate-limit Nominatim)

---

## Comandos habituales

```bash
# Arrancar stack
docker compose up --build -d

# Tests — deben pasar al 100% antes de cerrar una fase
docker compose exec api pytest

# Migraciones
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "desc"
# ⚠️ Revisar fichero generado: eliminar falsos positivos de índices GiST

# Rebuild completo (obligatorio si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Importar .fit en bulk
docker compose exec api python bulk_import.py --user-email EMAIL --path /activities

# Enriquecer nombres (post-bulk-import)
docker compose exec api python enrich_names.py --all-users
docker compose exec api python enrich_names.py --user-email EMAIL --force
```

## URLs locales

| Servicio | URL |
|---|---|
| API | http://localhost:8000 |
| Docs OpenAPI | http://localhost:8000/docs |
| Web | http://localhost:5173 |
| Adminer | http://localhost:8080 |
| Mailpit | http://localhost:8026 |
| DB | localhost:5432 (`fitapp`/`fitapp`) |
