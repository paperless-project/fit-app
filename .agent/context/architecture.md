# Arquitectura

## Estructura del repo
```
fit-app/
├── apps/api/          Python/FastAPI
│   ├── src/fitapp/
│   │   ├── auth/      users.py (fastapi-users config: backends JWT, JWT-remember, Google OAuth)
│   │   ├── models/    activity.py (Activity, Record, Lap)
│   │   │              user.py (User, OAuthAccount, StravaToken)
│   │   ├── routers/   activities.py, stats.py, account.py, strava.py,
│   │   │              google_callback.py, register.py
│   │   ├── schemas/   activity.py, stats.py, user.py, register.py
│   │   ├── services/  activity_service.py, fit_parser.py, fit_repair.py,
│   │   │              geocoding.py, email.py, otp.py, power_estimation.py,
│   │   │              strava_service.py
│   │   ├── config.py  Settings (pydantic-settings): postgres, jwt, smtp, google, strava
│   │   ├── db.py      engine, SessionLocal, AsyncSessionLocal(alias), get_session
│   │   └── main.py    FastAPI app; orden de routers importa (ver gotchas)
│   ├── alembic/       migraciones
│   ├── tests/         214 tests (pytest-asyncio, NullPool, conftest con mocks autouse)
│   ├── bulk_import.py CLI importación masiva .fit
│   └── enrich_names.py CLI enriquecimiento nombres geocoding
├── apps/web/          React 18 + Vite + TypeScript + Tailwind
│   └── src/
│       ├── components/  Layout, PrivateRoute, ActivityMap, ActivityCharts
│       ├── pages/       Login, Register, Verify, Activities, ActivityDetail,
│       │                Stats, Calendar, Account, OAuthCallback
│       ├── lib/         api.ts, auth.ts, activities.ts, stats.ts, strava.ts, account.ts
│       ├── store/       authStore.ts (Zustand)
│       └── types/       user.ts, activity.ts, stats.ts
├── .claude/commands/  skills: importar-strava, sync-docs, fase-gestion-cuenta, etc.
├── .agent/context/    documentación para agentes (este directorio)
└── doc/PLAN.md        plan técnico detallado
```

## Flujo principal: upload FIT
```
POST /activities/upload (multipart .fit)
  → parse_fit_safe() → ParsedFit (o repara CRC y reintenta)
  → persist_activity(db, user_id, parsed)
      → dedupe (user_id, file_hash) → 409 si existe
      → build_power_series() + compute_normalized_power()
      → INSERT activity (name=NULL) + records + laps → COMMIT
  → background_tasks.add_task(_enrich_name_bg, id)
  → 201 ActivityOut (inmediato)

_enrich_name_bg(id) [sesión propia, no bloquea upload]
  → generate_activity_name(records) → Nominatim → str|None
  → UPDATE activities.name
```

## Flujo Strava import
```
GET /strava/authorize (autenticado)
  → genera state = JWT(sub=user_id, aud="strava-oauth")
  → devuelve {authorization_url} con state embebido

→ usuario autoriza en Strava →

GET /strava/callback?code=...&state=... (sin auth)
  → decodifica state JWT → obtiene user_id
  → exchange_code(code) → {access_token, refresh_token, expires_at}
  → INSERT/UPDATE strava_tokens
  → redirect frontend /account?strava_connected=1

POST /strava/import (autenticado)
  → get_valid_access_token() (refresca si expires_at-60 < now)
  → background_tasks.add_task(_import_bg, user_id, access_token, after, before)

_import_bg() [sesión propia por actividad]
  → list_activities() paginado (100/página)
  → por actividad: get_activity_streams() + get_activity_laps()
  → strava_to_parsed() → ParsedFit (datetimes naive, hash=sha256("strava-{id}"))
  → persist_activity() → COMMIT (dedupe por file_hash)
  → _enrich_name_bg() si nueva
  → sleep(1.2s) entre actividades
  → al terminar: UPDATE strava_tokens.last_import_at
```

## Flujo auth Google OAuth2
```
GET /auth/google/authorize?flow=login|register
  → state JWT con {csrf_token, flow}
  → devuelve {authorization_url} + CSRF cookie

→ usuario autoriza en Google →

GET /auth/google/callback (custom, toma precedencia)
  → verifica CSRF cookie + state
  → get_id_email() → (account_id, email)
  → flow=login: busca usuario existente → JWT o error
  → flow=register: crea google_token → redirect /register?google_token=...
```

## Orden de routers en main.py (crítico)
```python
register.router          # /auth/register/* antes de fastapi-users
auth_backend (jwt)       # /auth/jwt/login|logout
auth_backend_remember    # /auth/jwt-remember/login
fastapi-users register   # /auth/register (simple, no usado)
fastapi-users verify     # /auth/verify
google_callback.router   # /auth/google/authorize|callback (custom, antes de fastapi-users)
fastapi-users oauth      # /auth/google/* (fastapi-users; no colisiona por precedencia)
account.router           # /users/me/password, DELETE /users/me (antes de fastapi-users /users/{id})
fastapi-users users      # /users/{id}
strava.router            # /strava/*
activities.router        # /activities/*
stats.router             # /stats/*
```

## Decisiones irreversibles
- Parsing en **backend** (Python)
- **PostgreSQL** + PostGIS (geography, ST_AsGeoJSON)
- **`fastapi-users`** para auth (JWT, Google OAuth, hashing)
- Geocoding via **Nominatim** (OSM, sin API key, rate-limit 1 req/s)
- Datetimes en BD como **TIMESTAMP naive UTC** (sin timezone)
- Strava: state JWT firmado para identificar usuario en callback sin sesión HTTP
