# API (FastAPI)

## Endpoints implementados

```
GET  /health
GET  /docs, /openapi.json

# Auth (fastapi-users)
POST /auth/register                   → crea usuario, envía email verificación automáticamente
POST /auth/jwt/login                  → {access_token, token_type:"bearer"}
POST /auth/jwt/logout
POST /auth/verify                     → {token} → is_verified=True
POST /auth/request-verify-token       → reenvía email verificación

# Usuarios
GET  /users/me
PATCH /users/me                       → email o password
GET|PATCH|DELETE /users/{id}          → solo superuser (403 para usuarios normales)

# Actividades
GET  /activities/                     → list[ActivityOut] del usuario autenticado, ordenado por started_at desc
POST /activities/upload               → multipart .fit → parsear → persistir; 409 duplicado, 400 inválido
GET  /activities/{id}                 → ActivityDetailOut (activity + records + laps)

# Stats (esqueleto)
GET  /stats/summary                   → {total_km:0, total_hours:0, total_activities:0}
```

## Schemas clave
```python
ActivityOut          # campos planos de Activity (sin records/laps)
ActivityDetailOut    # ActivityOut + records: list[RecordOut] + laps: list[LapOut]
RecordOut            # ts, lat, lon, altitude_m, distance_m, speed_mps, heart_rate, cadence, power
LapOut               # lap_index, start_time, duration_s, distance_m, avg_speed_mps, avg_hr, ascent_m
```

## Servicios clave
```
services/fit_parser.py     parse_fit(), parse_fit_safe() → ParsedFit dataclass
services/fit_repair.py     repair(path) → bytes; estrategias: check_crc=False + _apply_fixes, trim progresivo
services/geocoding.py      generate_activity_name(records) → str|None; Nominatim, caché dict, rate-limit 1.1s
services/activity_service.py  persist_activity() → dedupe hash, geocoding, dedup timestamps, flush+commit
services/email.py          send_verification_email() → SMTP async via asyncio.to_thread
```

## Gotchas implementación
- `ST_X`/`ST_Y` no aceptan `geography` → usar `func.ST_AsGeoJSON(Record.position)` + `json.loads()`
- Timestamps duplicados en records Garmin → deduplicar por `ts` en `persist_activity` antes de `db.add_all()`
- `db.rollback()` necesario en bulk_import tras cada error para no envenenar la sesión
- Mock geocoding en tests: `patch("fitapp.services.activity_service.generate_activity_name")`
- Mock email en tests: `patch("fitapp.auth.users.send_verification_email")`

## Tests
```
tests/conftest.py           NullPool, TRUNCATE entre tests, mock autouse email + geocoding
tests/test_smoke.py         /health, /openapi.json
tests/test_auth.py          register, login, /users/me, logout
tests/test_users.py         PATCH /users/me, rutas admin
tests/test_verification.py  flujo completo verificación email
tests/test_activities.py    GET /activities/ auth + aislamiento por usuario
tests/test_upload.py        POST /activities/upload (éxito, dup 409, inválido 400, auth)
tests/test_activity_detail.py  GET /activities/{id} (records, GPS, 404, aislamiento)
tests/test_stats.py         GET /stats/summary auth
tests/test_repair.py        CRC-16, repair bad CRC, truncado, irreparable
tests/test_geocoding.py     generate_activity_name (POIs, dedupe, fallbacks)
```
