# API (FastAPI)

## Endpoints registrados

```
GET  /health                          → {"status":"ok","version":"0.1.0"}
GET  /docs, /openapi.json

# Auth (fastapi-users)
POST /auth/register                   → crea usuario, envía email verificación
POST /auth/jwt/login                  → {access_token, token_type:"bearer"}
POST /auth/jwt/logout
POST /auth/verify                     → {token} → verifica email
POST /auth/request-verify-token       → {email} → reenvía email verificación

# Usuarios
GET  /users/me                        → usuario autenticado
PATCH /users/me                       → actualizar email/password
GET  /users/{id}                      → solo superuser (403 para usuarios normales)
PATCH /users/{id}                     → solo superuser
DELETE /users/{id}                    → solo superuser

# Recursos (ESQUELETOS)
GET  /activities/                     → [] (Fase 2)
GET  /stats/summary                   → {total_km:0, total_hours:0, total_activities:0} (Fase 5)
```

## Pendiente implementar (Fase 2+)
```
POST /activities/upload               multipart .fit → parsear → persistir
GET  /activities/{id}
GET  /activities/{id}/records
GET  /activities/{id}/laps
DELETE /activities/{id}
GET  /stats/calendar?year=YYYY        (Fase 5)
GET  /stats/timeline?bucket=month     (Fase 5)
```

## Auth
- `current_active_user = fastapi_users.current_user(active=True)` — inyectar como `Depends`
- Token: `Authorization: Bearer <token>`
- `validate_password`: mínimo 8 caracteres (InvalidPasswordException)
- `on_after_register` → llama `request_verify` → `on_after_request_verify` → envía email

## Email
- `services/email.py`: `send_verification_email(email, token)` — SMTP async via `asyncio.to_thread`
- No-op si `settings.smtp_host` está vacío
- En tests: parchear `fitapp.auth.users.send_verification_email` (autouse en conftest)

## Ficheros clave
```
src/fitapp/main.py              app FastAPI, monta routers
src/fitapp/config.py            pydantic-settings (POSTGRES_*, JWT_*, SMTP_*, FRONTEND_URL, CORS_*)
src/fitapp/db.py                engine async + get_session + Base
src/fitapp/auth/users.py        fastapi-users: UserManager, backends, current_active_user
src/fitapp/models/              User, Activity, Record, Lap
src/fitapp/schemas/             UserRead, UserCreate, UserUpdate
src/fitapp/routers/             activities.py, stats.py (esqueletos)
src/fitapp/services/email.py    send_verification_email()
src/fitapp/services/fit_parser.py  parse_fit() — ESQUELETO (solo hash)
```

## Tests
```
tests/conftest.py       NullPool engine, TRUNCATE entre tests, mock autouse de email
tests/test_smoke.py     /health, /openapi.json
tests/test_auth.py      register, login, /users/me, logout
tests/test_users.py     PATCH /users/me, rutas admin requieren superuser
tests/test_activities.py  GET /activities/ auth
tests/test_stats.py     GET /stats/summary auth
tests/test_verification.py  flujo completo verificación email
```
