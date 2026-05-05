# Arquitectura

## Estructura del repo
```
fit-app/
├── apps/api/          Python/FastAPI — src/fitapp/{auth,models,routers,services,schemas}
├── apps/web/          React/Vite — src/{components,pages,hooks,lib,types}
├── scripts/           bulk_import.py (CLI importación masiva)
└── doc/PLAN.md        Plan completo con fases, esquema BD, endpoints
```

## Flujo de datos
```
.fit file → POST /activities/upload (multipart)
         → fit_parser.parse_fit() → ParsedFit dataclass
         → persist Activity + Records + Laps (dedupe por user_id+file_hash)
         → GET /activities/{id}/records → frontend → Chart.js + Leaflet
```

## Multi-tenant
- Tabla `users` (fastapi-users UUID PK)
- Todos los recursos tienen `user_id FK → users(id) ON DELETE CASCADE`
- `UNIQUE(user_id, file_hash)` en `activities` — mismo fichero puede pertenecer a distintos usuarios
- Endpoints filtran siempre por `current_active_user` del JWT

## Decisiones irreversibles
- Parsing en backend (no en cliente)
- PostgreSQL + PostGIS (no MySQL, no SQLite)
- `fastapi-users` para auth (no JWT manual)
- `uv` como gestor de paquetes Python
- `pnpm` como gestor JS
