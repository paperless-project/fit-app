# Arquitectura

## Estructura del repo
```
fit-app/
├── apps/api/          Python/FastAPI — src/fitapp/{auth,models,routers,services,schemas}
├── apps/web/          React/Vite — src/{components,pages,lib,store,types}
├── scripts/           bulk_import.py (CLI importación masiva, pendiente)
└── doc/PLAN.md        Plan completo con fases, esquema BD, endpoints
```

## Flujo de datos (Fase 2 — pendiente)
```
.fit file → POST /activities/upload (multipart)
         → fit_parser.parse_fit() → ParsedFit dataclass
         → persist Activity + Records + Laps (dedupe por user_id+file_hash)
         → GET /activities/{id}/records → frontend → Chart.js + Leaflet
```

## Flujo de auth + verificación
```
POST /auth/register → UserManager.on_after_register
                    → request_verify() → on_after_request_verify
                    → send_verification_email() → SMTP → Mailpit (dev)
                    
usuario pincha enlace → /verify?token=TOKEN (frontend)
                      → POST /auth/verify (backend) → is_verified=True
```

## Multi-tenant
- Tabla `users` (fastapi-users, UUID PK)
- Todos los recursos tienen `user_id FK → users(id) ON DELETE CASCADE`
- `UNIQUE(user_id, file_hash)` en `activities` — mismo fichero puede ser de distintos usuarios
- Endpoints filtran siempre por `current_active_user` del JWT

## Decisiones irreversibles
- Parsing en backend (no en cliente)
- PostgreSQL + PostGIS (no MySQL, no SQLite)
- `fastapi-users` para auth (no JWT manual)
- `uv` como gestor de paquetes Python
- `pnpm` como gestor JS
- Verificación de email obligatoria al registrarse
