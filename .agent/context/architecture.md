# Arquitectura

## Estructura del repo
```
fit-app/
├── apps/api/          Python/FastAPI — src/fitapp/{auth,models,routers,schemas,services}
├── apps/web/          React/Vite — src/{components,pages,lib,store,types}
├── scripts/           bulk_import.py (CLI importación masiva)
└── doc/PLAN.md        Plan original con fases y esquema BD
```

## Flujo de datos principal
```
.fit file → POST /activities/upload (multipart)
          → parse_fit_safe()
              → parse_fit()           OK → ParsedFit
              → repair() si falla     → parse_fit() con fichero reparado
          → persist_activity()
              → generate_activity_name() → Nominatim OSM → name
              → deduplica timestamps (pk records)
              → INSERT activity + records + laps
          → ActivityOut

GET /activities/{id}
          → SELECT activity
          → SELECT records con ST_AsGeoJSON(position) → lat/lon
          → SELECT laps
          → ActivityDetailOut
```

## Flujo auth + verificación email
```
POST /auth/register → on_after_register → request_verify → on_after_request_verify
                    → send_verification_email(email, token) → SMTP → Mailpit (dev)

/verify?token=TOKEN → POST /auth/verify → is_verified=True
```

## Multi-tenant
- `user_id FK → users(id) ON DELETE CASCADE` en activities/records/laps
- `UNIQUE(user_id, file_hash)` en activities — mismo fichero = distinto usuario OK
- Todos los endpoints filtran por `current_active_user` del JWT

## Decisiones irreversibles
- Parsing en **backend**, no en cliente
- **PostgreSQL** + PostGIS
- **`fastapi-users`** para auth
- **`uv`** / **`pnpm`** como gestores de paquetes
- Verificación de email obligatoria al registrarse
- Nombres de actividad via **Nominatim** (OSM, gratuito, sin API key)
- FIT repair en **Python puro** (no depende de choochoo ni fit-java-sdk)
