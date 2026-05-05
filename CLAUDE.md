# fit-app — Memoria del proyecto

## Objetivo
App web para importar ficheros FIT (actividades ciclistas), almacenarlos en PostgreSQL y generar visualizaciones: mapa GPS, gráficas de velocidad/FC/cadencia/potencia/altitud, estadísticas agregadas. Multi-usuario con auth JWT.

Ficheros fuente en `/workspace/xabi/Activities/` (118 ficheros `.fit`). **Solo lectura** — no modificar.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + verificación email) |
| Email dev | Mailpit (SMTP local) |
| Parsing FIT | `fitparse` (en backend, pendiente) |
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
- **Tests usan `NullPool`** — sin reutilización de conexiones entre tests; evita "operation in progress" de asyncpg.
- **Mock de email en tests**: parchear `fitapp.auth.users.send_verification_email` (no `fitapp.services.email`).
- Puerto 1025 del host ocupado → Mailpit usa `1026:1025` (host:container). El api habla con mailpit por red interna en puerto 1025.

---

## Estado actual (2026-05-05)

### Fase 1 — Completa ✅ (35 tests pasando)

**Backend:**
- Stack Docker arranca con `docker compose up --build` (5 servicios: db, api, web, adminer, mailpit)
- BD schema completo: `users`, `activities`, `laps`, `records` + índices GiST
- Migración Alembic aplicada (rev `379c3241c147`)
- Auth completa vía `fastapi-users`:
  - `POST /auth/register` — crea usuario, envía email de verificación automáticamente
  - `POST /auth/jwt/login` / `POST /auth/jwt/logout`
  - `GET|PATCH /users/me`
  - `POST /auth/verify` — verifica token del email
  - `POST /auth/request-verify-token` — reenvía email de verificación
  - `GET|PATCH|DELETE /users/{id}` — solo superuser (403 para usuarios normales)
- `UserManager.validate_password`: mínimo 8 caracteres
- Servicio de email (`services/email.py`): SMTP async via `asyncio.to_thread`; no-op si `SMTP_HOST` vacío
- Mailpit en `http://localhost:8026` para capturar emails en dev

**Frontend:**
- `LoginPage` — formulario email/password, redirige a `/activities`
- `RegisterPage` — formulario con validación, redirige a `/login`
- `VerifyPage` — lee `?token=` de la URL, llama a `/auth/verify`, muestra éxito/error
- `PrivateRoute` — redirige a `/login` si no hay token; spinner mientras inicializa
- `Layout` — navbar con email del usuario y botón logout
- `authStore` (Zustand) — token en `localStorage`, hidratación en mount via `/users/me`
- Manejo global de 401 en `api.ts` — limpia token y redirige a `/login`

### Esqueletos (código presente, sin implementación real)
- `GET /activities/` → devuelve `[]`
- `GET /stats/summary` → devuelve `{total_km:0, total_hours:0, total_activities:0}`
- `services/fit_parser.py` → `parse_fit()` solo calcula SHA-256, no extrae datos FIT
- `scripts/bulk_import.py` → itera ficheros, no persiste
- `ActivitiesPage` → placeholder "Próximamente"

---

## Trabajo pendiente (Fase 2 →)

1. **Fase 2** — `fit_parser.py` real: extraer session/records/laps con `fitparse`
2. **Fase 2** — `POST /activities/upload`: multipart, parsear, persistir con dedupe `(user_id, file_hash)`
3. **Fase 2** — Completar `scripts/bulk_import.py`
4. **Fase 3** — Listado de actividades (tabla + filtros + paginación)
5. **Fase 4** — Detalle de actividad (mapa Leaflet + gráficas Chart.js sincronizadas)
6. **Fase 5** — Estadísticas agregadas (heatmap calendario, evolución mensual)

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

# Rebuild completo (si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Importar Activities/ (cuando esté implementado)
docker compose exec api python -m scripts.bulk_import --user-email tu@email.com --path /activities
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

## Referencia
- Plan completo: `doc/PLAN.md`
- Spec FIT: https://developer.garmin.com/fit/
- `fitparse`: https://github.com/dtcooper/python-fitparse
- `fastapi-users`: https://fastapi-users.github.io/fastapi-users/
