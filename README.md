# fit-app

Aplicación web para importar actividades ciclistas (ficheros FIT o desde Strava), almacenarlas en PostgreSQL+PostGIS y generar visualizaciones: mapa GPS, gráficas de altitud/velocidad/FC/cadencia/potencia, estadísticas agregadas, calendario TSS/IF y potencia normalizada. Multi-usuario con autenticación JWT.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + GeoAlchemy2 |
| Auth | `fastapi-users` (JWT + Google OAuth2 + verificación email) |
| Parsing FIT | `fitparse` + reparación CRC-16 propia |
| Geocoding | Nominatim OSM (sin API key) |
| Potencia | Estimación física (gravedad + aerodinámica + rodadura) |
| Strava | OAuth2 + import actividades via API (streams GPS/HR/potencia) |
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
# Editar .env con tus credenciales:
#   GOOGLE_OAUTH_CLIENT_ID/SECRET  (console.cloud.google.com → APIs & Services → Credentials)
#   STRAVA_CLIENT_ID/SECRET        (strava.com/settings/api — Authorization Callback Domain: localhost)

# 2. Levantar el stack completo
docker compose up --build -d

# 3. Aplicar migraciones
docker compose exec api alembic upgrade head

# 4. Instalar httpx-oauth (dependencia Google OAuth, tras cada rebuild)
docker compose exec api uv pip install --python /opt/venv "httpx-oauth>=0.15"
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

### Desde ficheros FIT (bulk)
```bash
# 1. Registrar un usuario desde la UI
# 2. Importar los ficheros .fit en bulk
docker compose exec api python bulk_import.py --user-email tu@email.com --path /activities

# 3. Enriquecer los nombres via geocoding inverso (Nominatim, ~1 min por actividad)
docker compose exec api python enrich_names.py --user-email tu@email.com
```

### Desde Strava
1. Configura `STRAVA_CLIENT_ID` y `STRAVA_CLIENT_SECRET` en `.env` y reinicia: `docker compose up -d api`
2. En la UI: **Mi cuenta → Strava → Conectar con Strava**
3. Pulsa **Importar actividades** (opcionalmente filtra por rango de fechas)

## Tests

```bash
docker compose exec api pytest
# → 214 tests pasando (22 ficheros)
```

## Desarrollo

```bash
# Nueva migración tras modificar models/
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar el fichero antes de aplicar: eliminar falsos positivos de índices GiST
docker compose exec api alembic upgrade head

# Rebuild completo (si cambia pyproject.toml)
docker compose down && docker volume rm fit-app_api_venv && docker compose up --build -d

# Reiniciar API (nueva variable de entorno en .env)
docker compose up -d api
```

## Estructura del repositorio

```
fit-app/
├── CLAUDE.md                    Contexto técnico y convenciones para sesiones de IA
├── doc/PLAN.md                  Plan de desarrollo y decisiones de arquitectura
├── .agent/context/              Documentación técnica detallada por área
│   ├── api.md                   Endpoints, schemas, servicios, mocks de tests
│   ├── architecture.md          Flujos de datos, orden de routers, decisiones irreversibles
│   ├── database.md              Esquema BD, migraciones, gotchas
│   ├── devops.md                Docker, comandos, variables de entorno
│   ├── frontend.md              Estructura React, componentes, convenciones
│   └── status.md                Estado de fases y trabajo pendiente
├── apps/api/                    Backend FastAPI
│   ├── src/fitapp/
│   │   ├── routers/             activities, stats, account, strava, google_callback, register
│   │   ├── services/            fit_parser, fit_repair, geocoding, activity_service,
│   │   │                        power_estimation, strava_service, otp, email
│   │   ├── models/              activity.py (Activity, Record, Lap)
│   │   │                        user.py (User, OAuthAccount, StravaToken)
│   │   └── schemas/             activity, stats, user, register
│   ├── alembic/versions/        7 migraciones Alembic
│   ├── tests/                   214 tests (22 ficheros)
│   ├── bulk_import.py           CLI importación masiva de .fit
│   └── enrich_names.py          CLI geocoding inverso de nombres
└── apps/web/                    Frontend React + Vite
    └── src/
        ├── pages/               Activities, ActivityDetail, Stats, Calendar, Account,
        │                        Login, Register, Verify, OAuthCallback
        ├── components/          ActivityMap, ActivityCharts, Layout, Pagination
        └── lib/                 activities, stats, account, strava, auth, api
```

## Funcionalidades implementadas

- **Registro multi-paso por email**: OTP 6 dígitos → perfil (nombre, apellidos, fecha nacimiento, género) + contraseña
- **Registro con Google**: OAuth2; nombre pre-rellenado desde Google; perfil completable después
- **Login**: email + contraseña, o Google OAuth2 (solo autentica cuentas existentes)
- **Recordarme**: sesión de 15 días
- **Perfil incompleto**: campanilla en navbar cuando faltan `birth_date` o `gender`
- **Upload FIT**: drag-and-drop, deduplicación por hash, reparación automática de CRC
- **Importación Strava**: OAuth2, import paginado de actividades con streams GPS/HR/cadencia/potencia, deduplicación por ID Strava
- **Listado**: paginado (20/página), filtros por nombre/deporte/fecha, exportar CSV
- **Detalle**: mapa Leaflet + gráficas sincronizadas (altitud, velocidad, FC, cadencia, potencia), tabla de vueltas, exportar GPX
- **Edición**: nombre, deporte, notas; borrado individual con confirmación
- **Nombres automáticos**: geocoding inverso Nominatim asíncrono — "Castillo de Olite desde Tafalla"
- **Potencia estimada**: física (gravedad + aerodinámica + rodadura) para actividades sin medidor
- **Potencia Normalizada (NP)**: calculada en tiempo de importación (Allen & Coggan, media móvil 30 s)
- **TSS e IF**: calculados en tiempo de consulta a partir de NP + FTP del usuario
- **Estadísticas**: totales (km/h/actividades/desnivel), heatmap GitHub-style, evolución mensual/anual
- **Calendario** (`/calendar`): cuadrícula de semanas con TSS/IF/distancia/tiempo/calorías por semana
- **Perfil de entrenamiento**: FTP y peso corporal; botón "Recalcular NP" para actividades históricas
- **Gestión de cuenta**: cambio de contraseña, desconectar Strava, borrado de cuenta con cascada

Contexto técnico completo en [`CLAUDE.md`](CLAUDE.md) y [`doc/PLAN.md`](doc/PLAN.md).
