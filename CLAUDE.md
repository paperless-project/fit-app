# fit-app — Memoria del proyecto

## Objetivo
App web para importar actividades ciclistas (ficheros FIT o desde Strava), almacenarlas en PostgreSQL+PostGIS y generar visualizaciones: mapa GPS, gráficas, estadísticas. Multi-usuario con auth JWT.

Ficheros FIT locales: `/workspace/xabi/Activities/` (118 ficheros, 114 `.fit`) → montados en `/activities:ro`. **No modificar.**

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + Google OAuth2 + verificación email) |
| Email dev | Mailpit (SMTP local, puerto 1026:1025) |
| Parsing FIT | `fitparse` + `services/fit_repair.py` (CRC-16 + trim progresivo) |
| Geocoding | `services/geocoding.py` (Nominatim OSM, 1 req/s, caché ~1km) |
| Strava | `services/strava_service.py` (OAuth2, streams, conversión → ParsedFit) |
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
- Datetimes en BD como **TIMESTAMP naive UTC** (sin tzinfo) — Strava devuelve ISO con Z, convertir con `_naive_utc()`
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
- **Timestamps duplicados en records Garmin** — deduplicar por `ts` antes de insertar
- **Mock de email**: `patch("fitapp.auth.users.send_verification_email")`
- **Mock de geocoding**: `patch("fitapp.services.activity_service.generate_activity_name")`
- **Mock de background task enrich**: `patch("fitapp.routers.activities._enrich_name_bg")` — parchear donde se USA
- Puerto 1025 del host ocupado → Mailpit usa `1026:1025`
- **`httpx-oauth` no persiste tras rebuild** — `docker compose exec api uv pip install --python /opt/venv "httpx-oauth>=0.15"` tras cada rebuild
- **FK `oauth_account.user_id` → `"users.id"`** — sobreescribir con `@declared_attr`
- **`on_after_register` con OAuth**: guardar `if not user.is_verified:` antes de llamar `request_verify()`
- **`get_access_token` hace HTTP real en tests** — parchear `google_oauth_client.get_access_token` con `AsyncMock`
- **CSRF cookie cross-origin**: fetch a `/auth/google/authorize` debe llevar `credentials: 'include'`
- **`csrf_token_cookie_secure=False`** en `get_oauth_router()` — obligatorio en HTTP dev
- **`User.oauth_accounts` necesita `cascade="all, delete-orphan"`** — sin esto SQLAlchemy intenta `UPDATE oauth_account SET user_id=NULL` (NOT NULL) al borrar el usuario
- **`/auth/google/authorize` sobreescrito en `google_callback.py`** — registrado ANTES del router fastapi-users
- **`get_authorization_url` de httpx_oauth usa `scope=` no `scopes=`**
- **Registro multi-paso no usa `user_manager.create()`** — usa `user_manager.user_db.create({...})` para evitar envío de email de verificación
- **Strava callback sin auth Bearer** — el user_id viaja en el state JWT firmado (`aud="strava-oauth"`)
- **Strava datetimes tienen tzinfo** — siempre convertir con `_naive_utc()` antes de insertar en BD
- **Strava rate limit 429** — 600 req/15min; el retry en `_get()` espera máx 15 s; importaciones grandes requieren ~1.2 s entre actividades
- **uvicorn --reload espera BackgroundTasks** — si hay un import de Strava activo con sleeps, el reload queda bloqueado hasta que termine
- **Nueva variable de entorno** — añadir siempre en `docker-compose.yml` (bloque `environment`) Y en `.env.example`
- **`AsyncSessionLocal = SessionLocal`** alias en `db.py` — usado por background tasks (`_import_bg`, `_enrich_name_bg`)

---

## Estado actual (2026-05-08) — 218 tests

### Fase 1 ✅ — Auth
Register + verify email + login/logout + `/users/me`. Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore (Zustand).

### Fase 2 ✅ — Parser FIT + Upload
`parse_fit()` + `parse_fit_safe()` + `fit_repair.py` (CRC-16 + trim). `POST /activities/upload`. `bulk_import.py`: 114/114 importados.

### Fase 3 ✅ — Listado frontend + nombres
`geocoding.py`: Nominatim, caché dict, rate-limit 1.1s. Columna `name` (migración `6bf7f63a1065`). ActivitiesPage.

### Fase 4 ✅ — Detalle de actividad
`GET /activities/{id}`: activity + records + laps. ActivityDetailPage: stats, mapa Leaflet, gráficas Chart.js sincronizadas.

### Fase 5 ✅ — Dashboard estadísticas
`/stats/summary+calendar+timeline`. StatsPage: tarjetas, heatmap GitHub-style, barras mensuales.

### Fase 6 ✅ — Filtros, edición, exportación
Filtros + paginación en `GET /activities/`. `GET /activities/sports`. `PATCH /activities/{id}` (migración `472807ab1cee`). CSV + GPX. Frontend: FilterBar, Pagination, EditModal.

### Fase 7 ✅ — Enriquecimiento asíncrono
BackgroundTasks geocoding post-upload. `POST /activities/enrich-names`. `enrich_names.py` CLI.

### Fase 8 ✅ — Gestión de cuenta
`PATCH /users/me/password`, `DELETE /users/me`, `DELETE /activities/{id}`, `DELETE /activities` (borrar todas). AccountPage con zona de peligro (dos filas: borrar actividades / borrar cuenta).

### Mejoras login ✅
JWT 256 bits / 8 h. Recordarme 15 días. Google OAuth2 (`flow=login|register`). OAuthCallbackPage. Paginación GET /activities/.

### Registro multi-paso ✅
3 pasos OTP email: `send-otp` → `verify-otp` → `complete`. Google `flow=register` → `complete-google`. Campos perfil (`first_name`, `last_name`, `birth_date`, `gender`). Campanilla "Faltan datos". Migración `159b99c22872`.

### Correcciones OAuth ✅
`cascade="all, delete-orphan"` en `User.oauth_accounts`. Separación login/registro. Manejo `ReadTimeout`.

### Fase 9 ✅ — Calendario + Potencia + TSS/IF
`services/power_estimation.py`. `normalized_power` en activities, `ftp`+`weight_kg` en users (migración `fa3c8e7b1d2a`). `GET /stats/calendar-detail`. `POST /stats/recalculate-np`. `PATCH /users/me/training`. CalendarPage.

### Integración Strava ✅ — 218 tests
- **Modelo**: `StravaToken` en `models/user.py` (migración `fb9a4f2c9133`); `import_status` + `import_status_message` (migración `fa4b4510841b`)
- **Columna**: `Activity.streams_fetched` bool (migración `d1c777f08bfa`) — indica si los streams GPS ya se descargaron
- **Servicio**: `services/strava_service.py` — OAuth2, `StravaRateLimitError` (429 con `retry_after`/`is_daily`), `strava_to_parsed()` + funciones extraídas `parse_strava_records()`, `parse_strava_laps()`, `build_bbox_wkt()`; deduplicación `sha256("strava-{id}")`
- **Router**: `routers/strava.py` — 5 endpoints; callback sin auth (state JWT con user_id); `_import_bg` bifásico: Fase 1 summaries (sin streams, rápido) → Fase 2 streams GPS en background
- **Deduplicación cross-source**: `persist_activity()` también deduplica por `started_at ±60 s` para evitar duplicados FIT+Strava de la misma salida
- **Nombres preservados**: las actividades importadas desde Strava conservan su nombre original (no se sobreescriben con geocoding)
- **Estados importación**: `running` → `fetching_streams` → `completed`; también `rate_limited`, `daily_limit`, `error`
- **Frontend**: botón "Actualizar desde Strava" (sin filtro fechas), banners de estado por fase, polling activo durante `running`/`fetching_streams`/`rate_limited`, invalidación de caché en transición de fase
- **Script limpieza**: `deduplicate_activities.py` — elimina duplicados FIT+Strava existentes con ventana ±60 s; soporta `--dry-run`/`--all-users`/`--user-email`
- **Config**: `STRAVA_CLIENT_ID/SECRET` en `docker-compose.yml` y `.env.example`

---

## Bugs conocidos / trabajo pendiente

- **uvicorn --reload bloqueado con sleep de rate limit** — si hay un import de Strava activo que llegó al rate limit (sleep 900 s), uvicorn queda bloqueado al detectar cambios. Solución: `docker compose restart api`.
- **`streams_fetched=False` si se interrumpe fase 2** — las actividades importadas en fase 1 que no llegaron a la fase 2 quedan sin GPS. Se resolverán en la siguiente sincronización (se reintenta desde `streams_fetched=False`).
- **114 actividades FIT con `name IS NULL`** → ejecutar `docker compose exec api python enrich_names.py --all-users`
- **`httpx-oauth` requiere instalación manual** tras rebuild: `docker compose exec api uv pip install --python /opt/venv "httpx-oauth>=0.15"`

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
# ⚠️ Revisar fichero: eliminar drop_index de índices GiST (falsos positivos)

# Rebuild completo (obligatorio si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Reiniciar api (nueva variable de entorno)
docker compose up -d api

# Importar .fit en bulk
docker compose exec api python bulk_import.py --user-email EMAIL --path /activities

# Enriquecer nombres (post-bulk-import)
docker compose exec api python enrich_names.py --all-users
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
