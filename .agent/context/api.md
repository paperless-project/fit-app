# API (FastAPI)

## Endpoints registrados
```
GET  /health                   → {"status":"ok","version":"0.1.0"}
GET  /docs                     → Swagger UI
GET  /openapi.json

POST /auth/register            → fastapi-users: crea usuario
POST /auth/jwt/login           → devuelve access_token (Bearer)
POST /auth/jwt/logout
GET  /users/me                 → usuario autenticado
GET  /users/{id}               → admin only

GET  /activities/              → [] (ESQUELETO)
GET  /stats/summary            → {total_km:0,...} (ESQUELETO)
```

## Pendiente añadir
```
POST /activities/upload        multipart .fit → parsear → persistir
GET  /activities/{id}
GET  /activities/{id}/records
GET  /activities/{id}/laps
DELETE /activities/{id}
GET  /stats/calendar?year=YYYY
GET  /stats/timeline?bucket=month|week
```

## Auth
- `current_active_user = fastapi_users.current_user(active=True)` — inyectar como `Depends`
- Token en header: `Authorization: Bearer <token>`
- `JWT_SECRET` en `.env` — cambiar en producción
- `JWT_LIFETIME_SECONDS` default 3600

## Ficheros clave
```
src/fitapp/main.py          app FastAPI, monta routers
src/fitapp/config.py        pydantic-settings (POSTGRES_*, JWT_*, CORS_*, ACTIVITIES_DIR)
src/fitapp/db.py            engine async + SessionLocal + Base declarativa
src/fitapp/auth/users.py    fastapi-users config completa
src/fitapp/models/          User, Activity, Record, Lap
src/fitapp/schemas/         UserRead, UserCreate, UserUpdate (fastapi-users)
src/fitapp/routers/         activities.py, stats.py (esqueletos)
src/fitapp/services/fit_parser.py  parse_fit() — solo hash, SIN parseo real
```

## Convenciones
- Toda ruta que devuelva datos de usuario filtra por `user.id` del JWT
- Respuestas con paginación para listas largas (pendiente implementar)
- `file_hash` = SHA-256 del fichero .fit (64 hex chars)
