# API (FastAPI)

## Endpoints implementados

```
GET  /health

# Auth (fastapi-users)
POST /auth/register
POST /auth/jwt/login              → {access_token} — token 8 h
POST /auth/jwt-remember/login     → {access_token} — token 15 días
POST /auth/jwt/logout
POST /auth/verify                 → {token} → is_verified=True

# Google OAuth2
GET  /auth/google/authorize       ?flow=login|register → JSON {authorization_url}
GET  /auth/google/callback        valida state JWT; login si existe o redirige con token/error

# Registro multi-paso OTP
POST /auth/register/send-otp      {email} → envía código 6 dígitos
POST /auth/register/verify-otp   {email, code} → {verified_token} JWT 30 min
POST /auth/register/complete     {verified_token, first_name, last_name, birth_date, gender, password}
POST /auth/register/complete-google  {google_token} → {access_token}

# Perfil / cuenta
GET   /users/me
PATCH /users/me
PATCH /users/me/password         {current_password, new_password ≥8} → 200/400/422
PATCH /users/me/training         {ftp?, weight_kg?}
DELETE /users/me                 {confirm: true} → 204; cascade activities + oauth_accounts

# Actividades
GET    /activities/              paginado {items,total,page,size,pages}; filtros: q,sport,date_from,date_to
GET    /activities/sports        lista deportes distintos del usuario
POST   /activities/upload        multipart .fit → 201; 409 dup; 400 inválido; encola enrich bg
POST   /activities/enrich-names  encola geocoding para name IS NULL del usuario
GET    /activities/export/csv    CSV con mismos filtros
GET    /activities/{id}          ActivityDetailOut (activity + records + laps)
PATCH  /activities/{id}          name?, sport?, notes?
DELETE /activities/{id}          204/403/404
GET    /activities/{id}/export/gpx  GPX 1.1 Garmin

# Estadísticas
GET /stats/summary
GET /stats/calendar?year=YYYY
GET /stats/calendar-detail?year=YYYY   actividades/día + resúmenes semanales (TSS, IF, dist, tiempo)
GET /stats/timeline?bucket=month|year
POST /stats/recalculate-np             recalcula NP en background para todas las actividades del usuario

# Strava
GET    /strava/authorize         requiere auth → JSON {authorization_url}; state=JWT(user_id)
GET    /strava/callback          NO requiere auth; decodifica state JWT; guarda tokens; redirect frontend
GET    /strava/status            {connected, athlete_id?, last_import_at?}
DELETE /strava/disconnect        204
POST   /strava/import            ?after=epoch&before=epoch → encola _import_bg en background
```

**CRÍTICO — orden de rutas:**
- `/activities/export/csv` y `/activities/sports` deben registrarse ANTES de `/{id}`
- `/strava/authorize`, `/strava/callback`, etc. ANTES de fastapi-users

## Schemas clave
```python
ActivityOut        id, name, sport, notes, started_at, distance_m, duration_s, moving_time_s,
                   ascent_m, avg_speed_mps, avg_hr, avg_power, normalized_power, calories, file_name
ActivityPatch      name?, sport?, notes?
ActivityDetailOut  ActivityOut + records: list[RecordOut] + laps: list[LapOut]
RecordOut          ts, lat, lon, altitude_m, distance_m, speed_mps, heart_rate, cadence, power
LapOut             lap_index, start_time, duration_s, distance_m, avg_speed_mps, avg_hr, ascent_m
UserRead           id, email, first_name, last_name, birth_date, gender, ftp, weight_kg, is_verified
CalendarDetailResponse  year, weeks, year_summary
```

## Servicios clave
```
services/fit_parser.py       parse_fit(), parse_fit_safe() → ParsedFit dataclass
services/fit_repair.py       repair(path) → bytes; CRC-16 + trim progresivo
services/geocoding.py        generate_activity_name(records) → str|None; caché ~1km; rate-limit 1.1s
services/activity_service.py persist_activity(db, user_id, parsed) → (Activity, is_dup)
                             enrich_activity_name(db, id, force=False) → bool
                             _enrich_name_bg(id) — tarea de fondo con AsyncSessionLocal propio
services/power_estimation.py build_power_series(records, mass_kg), compute_normalized_power(powers)
services/strava_service.py   OAuth2, _get() con retry 429, list_activities(), get_activity_streams(),
                             get_activity_laps(), strava_to_parsed() → ParsedFit, strava_hash()
services/otp.py              create_otp, verify_otp, create_verified_token, decode_verified_token,
                             create_google_registration_token, decode_google_registration_token
services/email.py            send_verification_email() — SMTP async
```

## Mocks en tests
```python
patch("fitapp.auth.users.send_verification_email")                     # email
patch("fitapp.services.activity_service.generate_activity_name")       # geocoding
patch("fitapp.routers.activities._enrich_name_bg")                     # enrich bg (donde se USA, no donde se define)
patch("fitapp.routers.strava.ss.exchange_code")                        # Strava OAuth
patch("fitapp.routers.strava._import_bg")                              # Strava import bg
patch.object(google_oauth_client, "get_access_token")                  # Google OAuth
patch.object(google_oauth_client, "get_id_email")                      # Google OAuth
```

## Gotchas
- `ST_X/ST_Y` no aceptan `geography` → usar `ST_AsGeoJSON` + `json.loads()`
- Timestamps duplicados Garmin → deduplicar por `ts` antes de `db.add_all()`
- Strava devuelve datetimes con tzinfo → convertir a naive con `_naive_utc()` antes de INSERT
- `AsyncSessionLocal = SessionLocal` alias en `db.py` (usado por background tasks)
- Strava callback NO requiere auth Bearer — el user_id va en el state JWT firmado
