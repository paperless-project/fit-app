# fit-app — Memoria del proyecto

## Objetivo
App web para importar ficheros FIT (actividades ciclistas), almacenarlos en PostgreSQL y generar visualizaciones: mapa GPS, gráficas de velocidad/FC/cadencia/potencia/altitud, estadísticas agregadas. Multi-usuario con auth JWT.

Ficheros fuente en `/workspace/xabi/Activities/` (118 ficheros, 114 `.fit`). **Solo lectura** — no modificar.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + verificación email) |
| Email dev | Mailpit (SMTP local) |
| Parsing FIT | `fitparse` |
| Reparación FIT | `services/fit_repair.py` (CRC-16 + trim progresivo, inspirado en choochoo) |
| Geocoding | `services/geocoding.py` (Nominatim OSM, rate-limit 1 req/s, caché ~1km) |
| BD | PostgreSQL 16 + PostGIS (`postgis/postgis:16-3.4`) |
| Frontend | React 18 + Vite + TypeScript + Tailwind + Chart.js + Leaflet + TanStack Query + Zustand |
| Infra dev | Docker Compose (`db`, `api`, `web`, `adminer`, `mailpit`) |
| Paquetes Python | `uv` |
| Paquetes JS | `pnpm` |

---

## Decisiones clave (no preguntar de nuevo)

- Parsing en **backend**, no en cliente.
- BD: **PostgreSQL** (no MySQL ni SQLite).
- Auth: **`fastapi-users`**, no JWT manual.
- Import masivo inicial: **CLI** (`scripts/bulk_import.py`), no UI.
- Multi-usuario desde el inicio: `user_id` FK en `activities`.
- `/workspace/xabi/Activities` montado en el contenedor como `/activities` (read-only).
- **Una fase no se da por completada hasta que todos los tests pasen.**

---

## Gotchas técnicos críticos

- **Venv en `/opt/venv`** — el volumen dev monta `/app` y taparía `/app/.venv`.
- **`PYTHONPATH=/app/src`** en `docker-compose.yml` — uv editable install no crea `.pth` correctamente.
- **`spatial_index=False`** en todos los `Geography(...)` — GeoAlchemy2 crea índices automáticos que colisionan con los de Alembic.
- **`include_object` en `alembic/env.py`** — filtra ~35 tablas PostGIS/Tiger del autogenerate.
- Nunca `Base.metadata.create_all()` — siempre Alembic.
- Extensiones (`uuid-ossp`, `postgis`, `citext`) se crean en la primera migración.
- **Tests usan `NullPool`** — sin reutilización de conexiones entre tests.
- **Mock de email en tests**: parchear `fitapp.auth.users.send_verification_email`.
- **Mock de geocoding en tests**: parchear `fitapp.services.activity_service.generate_activity_name`.
- **`ST_X`/`ST_Y` no funcionan sobre `geography`** — usar `ST_AsGeoJSON` y parsear JSON.
- **Timestamps duplicados en records** — algunos dispositivos Garmin repiten el mismo segundo; deduplicar por `ts` antes de insertar (ya corregido en `activity_service.py`).
- Puerto 1025 del host ocupado → Mailpit usa `1026:1025`.
- **`scripts/bulk_import.py` requiere `PYTHONPATH=/app/src`** y ejecutarse desde `/app` dentro del contenedor.

---

## Estado actual (2026-05-06)

### Fase 1 — Completa ✅
Auth completa (register + verify email + login/logout + `/users/me`). Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout.

### Fase 2 — Completa ✅
- `parse_fit()`: extrae session/records/laps, convierte semicírculos→grados, genera WKT.
- `parse_fit_safe()`: intenta parsear; si falla, repara y reintenta; preserva hash original.
- `fit_repair.py`: CRC-16 FIT + trim progresivo hasta 8192 bytes (inspirado en choochoo).
- `POST /activities/upload`: multipart, dedupe por `(user_id, file_hash)`, 409 duplicado.
- `scripts/bulk_import.py`: importa 114/114 ficheros sin errores.
- `GET /activities/`: lista actividades del usuario autenticado.

### Fase 3 — Completa ✅
- Nombres de actividad generados automáticamente via Nominatim OSM: "POI1, POI2 y POI3 desde StartLocality".
- Columna `name` en `activities` (migración `6bf7f63a1065`).
- `ActivitiesPage`: tabla con Fecha, Actividad (nombre/deporte), Distancia, Duración, Desnivel, Vel. media, FC media, Calorías.
- Modal drag-and-drop para subir ficheros `.fit`.
- Filas clicables → navegan a detalle.

### Fase 4 — Completa ✅
- `GET /activities/{id}`: devuelve actividad + records (lat/lon via `ST_AsGeoJSON`) + laps.
- `ActivityDetailPage`: cabecera con stats, mapa Leaflet con traza GPS, gráficas Chart.js sincronizadas, tabla de vueltas.
- `ActivityMap`: polyline GPS, marcadores inicio/fin, punto móvil sincronizado con gráficas.
- `ActivityCharts`: altitud, velocidad, FC, cadencia, potencia; crosshair sincronizado; tooltip con distancia.

**Tests: 77 pasando.**

---

## Trabajo pendiente

### Fase 5 — Dashboard de estadísticas
- `GET /stats/summary`: total km, horas, actividades, desnivel
- `GET /stats/calendar?year=YYYY`: heatmap tipo GitHub
- `GET /stats/timeline?bucket=month`: evolución mensual de km/horas
- Frontend: página Stats con heatmap calendario + gráficos de tendencia

### Mejoras conocidas / bugs
- Los nombres de actividad de las 114 actividades importadas en bulk son `NULL` (el geocoding en bulk_import tarda mucho por el rate-limit de Nominatim; considerar job asíncrono o comando separado de "enriquecer nombres").
- `apps/api/bulk_import.py` es un fichero huérfano (copia temporal usada para ejecutar en el contenedor); ignorar o borrar.
- `JWT_SECRET` en dev tiene 30 bytes (warning InsecureKeyLengthWarning); usar ≥32 bytes en producción.
- No hay paginación en `GET /activities/` (irrelevante con 114 actividades, problema futuro con más datos).

---

## Comandos habituales

```bash
# Arrancar stack
docker compose up --build

# Tests (deben pasar al 100% antes de cerrar una fase)
docker compose exec api pytest

# Aplicar migraciones
docker compose exec api alembic upgrade head

# Nueva migración (tras tocar models/)
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar el fichero generado: el autogenerate detecta falsos positivos con índices GiST

# Rebuild completo (si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Importar Activities/ (el script vive en apps/api/bulk_import.py → /app/bulk_import.py en el contenedor)
docker compose exec api python bulk_import.py --user-email EMAIL --path /activities
```

## URLs locales

| Servicio | URL |
|---|---|
| API | http://localhost:8000 |
| Docs OpenAPI | http://localhost:8000/docs |
| Web | http://localhost:5173 |
| Adminer | http://localhost:8080 |
| Mailpit (dev email) | http://localhost:8026 |
| DB | localhost:5432 (user/pass: `fitapp`) |
