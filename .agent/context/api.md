# API (FastAPI)

## Endpoints implementados

```
GET  /health
GET  /docs, /openapi.json

# Auth (fastapi-users)
POST /auth/register               → 201, envía email verificación
POST /auth/jwt/login              → {access_token, token_type}
POST /auth/jwt/logout
POST /auth/verify                 → {token} → is_verified=True
POST /auth/request-verify-token

# Usuarios
GET   /users/me
PATCH /users/me                   → email o password
GET|PATCH|DELETE /users/{id}      → solo superuser

# Actividades
GET  /activities/                 → list[ActivityOut], filtros: q, sport, date_from, date_to
POST /activities/upload           → 201 ActivityOut; 409 duplicado; 400 inválido; encola enrich bg
POST /activities/enrich-names     → {"queued": N} — encola geocoding para name IS NULL del usuario
GET  /activities/export/csv       → CSV con mismos filtros que GET /activities/
GET  /activities/{id}             → ActivityDetailOut (activity + records + laps)
PATCH /activities/{id}            → edición parcial: name, sport, notes (exclude_unset=True)
GET  /activities/{id}/export/gpx  → GPX 1.1 con extensiones Garmin (hr, cad, power)

# Estadísticas
GET  /stats/summary               → {total_activities, total_km, total_hours, total_ascent_m}
GET  /stats/calendar?year=YYYY    → {year, days: {"YYYY-MM-DD": {count, km}}}
GET  /stats/timeline?bucket=month|year → list[{period, count, km, hours, ascent_m}]
```

**CRÍTICO — orden de rutas en activities router:**
`/export/csv` debe registrarse ANTES de `/{activity_id}` para evitar que "export" se parsee como UUID.

## Schemas clave
```python
ActivityOut       # campos planos; incluye: id, name, sport, notes, started_at, distance_m,
                  # duration_s, moving_time_s, ascent_m, avg_speed_mps, avg_hr, calories, file_name
ActivityPatch     # name?, sport?, notes? — todos opcionales
ActivityDetailOut # ActivityOut + records: list[RecordOut] + laps: list[LapOut]
RecordOut         # ts, lat, lon, altitude_m, distance_m, speed_mps, heart_rate, cadence, power
LapOut            # lap_index, start_time, duration_s, distance_m, avg_speed_mps, avg_hr, ascent_m
StatsSummary      # total_activities, total_km, total_hours, total_ascent_m
CalendarResponse  # year, days: dict[str, CalendarDay]
TimelineEntry     # period, count, km, hours, ascent_m
```

## Servicios clave
```
services/fit_parser.py      parse_fit(), parse_fit_safe() → ParsedFit dataclass
services/fit_repair.py      repair(path) → bytes; CRC-16 + trim progresivo hasta 8192 bytes
services/geocoding.py       generate_activity_name(records) → str|None
                            _reverse(lat, lon, zoom) → dict|None (caché + rate-limit 1.1s)
                            _haversine_km(), _locality(), _poi_name(), _join_pois()
services/activity_service.py  persist_activity() — dedupe, INSERT sin geocoding
                              enrich_activity_name(db, id, force=False) → bool
                              _enrich_name_bg(id) — tarea de fondo con SessionLocal propio
services/email.py           send_verification_email() → SMTP async via asyncio.to_thread
```

## Gotchas implementación
- `ST_X`/`ST_Y` no aceptan `geography` → usar `func.ST_AsGeoJSON(Record.position)` + `json.loads()`
- Timestamps duplicados Garmin → deduplicar por `ts` antes de `db.add_all()` en persist_activity
- `db.rollback()` necesario en bulk_import tras cada error
- Mock geocoding: `patch("fitapp.services.activity_service.generate_activity_name")`
- Mock email: `patch("fitapp.auth.users.send_verification_email")`
- Mock enrich bg: `patch("fitapp.routers.activities._enrich_name_bg")` — NO `activity_service._enrich_name_bg`
  (el router hace `from ... import _enrich_name_bg` creando binding local; el mock debe apuntar ahí)

## Tests (119 en total)
```
tests/conftest.py              NullPool, TRUNCATE entre tests, mocks autouse: email + geocoding + enrich_bg
tests/test_smoke.py            /health, /openapi.json
tests/test_auth.py             register, login, /users/me, logout
tests/test_activities.py       GET /activities/ auth + aislamiento
tests/test_activity_detail.py  GET /activities/{id} (records, GPS, 404, aislamiento)
tests/test_activity_edit.py    PATCH /activities/{id} parcial, aislamiento
tests/test_activity_export.py  GPX, CSV, filtros CSV, auth
tests/test_activity_filters.py sport, date_from, date_to, q
tests/test_upload.py           upload éxito/dup/inválido; parse_fit; bbox/start_point WKT
tests/test_enrich_names.py     bg task resultado, force, skip, endpoint enrich-names, aislamiento
tests/test_geocoding.py        generate_activity_name (locality, POIs, dedupe, fallos)
tests/test_repair.py           CRC-16, repair bad CRC, truncado, irreparable
tests/test_stats.py            summary, calendar, timeline; auth; aislamiento
```
