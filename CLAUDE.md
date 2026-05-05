# fit-app — Memoria del proyecto

## Objetivo
App web para importar ficheros FIT (actividades ciclistas), almacenarlos en PostgreSQL y generar visualizaciones: mapa GPS, gráficas de velocidad/FC/cadencia/potencia/altitud, estadísticas agregadas. Multi-usuario con auth JWT.

Ficheros fuente en `/workspace/xabi/Activities/` (118 ficheros `.fit`). **Solo lectura** — no modificar.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT) |
| Parsing FIT | `fitparse` (en backend) |
| BD | PostgreSQL 16 + PostGIS (`postgis/postgis:16-3.4`) |
| Frontend | React 18 + Vite + TypeScript + Tailwind + Chart.js + Leaflet + TanStack Query |
| Infra dev | Docker Compose (`db`, `api`, `web`, `adminer`) |
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

---

## Gotchas técnicos críticos

- **Venv en `/opt/venv`**, no en `/app/.venv` — el volumen dev monta `/app` y taparía el venv.
- **`PYTHONPATH=/app/src`** en `docker-compose.yml` — el install editable con `uv` no crea `.pth` correctamente al hacer `COPY src/` post-install.
- **`spatial_index=False`** en todos los `Geography(...)` de los modelos — GeoAlchemy2 crea índices automáticos al hacer `CREATE TABLE`, colisionando con los que Alembic crea explícitamente. Los índices GiST van en la migración como `op.create_index(..., postgresql_using='gist')`.
- **`include_object` en `alembic/env.py`** — filtra las tablas PostGIS/Tiger del autogenerate. Sin él, Alembic detecta ~35 tablas ajenas como "removed".
- Nunca usar `Base.metadata.create_all()` — siempre Alembic.
- Extensiones (`uuid-ossp`, `postgis`, `citext`) se crean en la primera migración, no en el Dockerfile.

---

## Estado actual (2026-05-05)

### Funcionando
- `docker compose up --build` arranca los 4 servicios
- API responde en `:8000` (`/health`, `/docs`, `/openapi.json`)
- Auth endpoints registrados (`/auth/register`, `/auth/jwt/login`, `/auth/jwt/logout`, `/users/me`)
- BD con schema completo: `users`, `activities`, `laps`, `records` + índices GiST
- Frontend Vite arranca en `:5173`, consulta `/health` y muestra estado del backend
- Adminer en `:8080`

### Esqueletos (sin implementar)
- `GET /activities/` → devuelve `[]`
- `GET /stats/summary` → devuelve ceros
- `fitapp/services/fit_parser.py` → `parse_fit()` solo calcula hash, no parsea FIT real
- `scripts/bulk_import.py` → itera ficheros y calcula hashes pero no persiste nada
- Frontend: no hay login, ni listado de actividades, ni detalle, ni gráficas

---

## Trabajo pendiente inmediato (Fase 1 → 2)

1. **Auth frontend**: página login, guard de rutas, almacenar JWT en `localStorage`.
2. **`fit_parser.py`**: implementar parseo real con `fitparse` — extraer session, records, laps.
3. **`POST /activities/upload`**: endpoint multipart, llamar al parser, persistir con dedupe por `(user_id, file_hash)`.
4. **`scripts/bulk_import.py`**: completar con persistencia real.
5. **Tests**: `tests/conftest.py` necesita un Postgres de test real (en Docker); los smoke tests fallan sin BD.

---

## Comandos habituales

```bash
# Arrancar stack
docker compose up --build

# Aplicar migraciones
docker compose exec api alembic upgrade head

# Nueva migración (tras tocar models/)
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Tests
docker compose exec api pytest

# Importar Activities/ (cuando esté implementado)
docker compose exec api python -m scripts.bulk_import --user-email tu@email.com --path /activities

# Regenerar cliente TS desde OpenAPI
docker compose exec web pnpm run gen:api
```

## URLs locales

| Servicio | URL |
|---|---|
| API | http://localhost:8000 |
| Docs OpenAPI | http://localhost:8000/docs |
| Web | http://localhost:5173 |
| Adminer (dev) | http://localhost:8080 |
| DB | localhost:5432 (user/pass: `fitapp`) |

## Referencia
- Plan completo: `doc/PLAN.md`
- Spec FIT: https://developer.garmin.com/fit/
- `fitparse`: https://github.com/dtcooper/python-fitparse
- `fastapi-users`: https://fastapi-users.github.io/fastapi-users/
