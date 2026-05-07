# Estado actual y trabajo pendiente

_Última actualización: 2026-05-07 — 214 tests_

## Fases completadas

### Fase 1 ✅ — Auth
fastapi-users, JWT (8 h / 15 días "recordarme"), verificación email, `/users/me`.
Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore (Zustand).

### Fase 2 ✅ — Parser FIT + Upload
`parse_fit()` + `parse_fit_safe()` + `fit_repair.py` (CRC-16 + trim 8192 bytes).
`POST /activities/upload`: multipart, dedupe `(user_id, file_hash)`, 409/400.
`bulk_import.py` CLI: 114/114 importados.

### Fase 3 ✅ — Listado frontend + nombres
`geocoding.py`: Nominatim OSM, rate-limit 1.1 s, caché ~1 km, start+end locality + 5 waypoints POI.
Migración `6bf7f63a1065`: columna `name`.
ActivitiesPage: tabla, modal upload drag-and-drop, filas clicables.

### Fase 4 ✅ — Detalle de actividad
`GET /activities/{id}`: activity + records (ST_AsGeoJSON) + laps.
ActivityDetailPage: stats, mapa Leaflet, gráficas Chart.js sincronizadas, tabla vueltas.

### Fase 5 ✅ — Dashboard estadísticas
`/stats/summary`, `/stats/calendar`, `/stats/timeline`.
StatsPage: tarjetas, heatmap GitHub-style, barras mensuales.

### Fase 6 ✅ — Filtros, edición, exportación
Filtros `GET /activities/`: q, sport, date_from, date_to, page, size (paginación).
`PATCH /activities/{id}`: name/sport/notes (migración `472807ab1cee`).
`GET /activities/export/csv`, `GET /activities/{id}/export/gpx`.
`GET /activities/sports`.

### Fase 7 ✅ — Enriquecimiento asíncrono
`BackgroundTasks` post-upload → `_enrich_name_bg(id)` con sesión propia.
`POST /activities/enrich-names`: encola name IS NULL del usuario.
`enrich_names.py` CLI.

### Fase 8 ✅ — Gestión de cuenta
`PATCH /users/me/password`, `DELETE /users/me` (cascade), `DELETE /activities/{id}`.
AccountPage: cambio contraseña + zona de peligro (confirmar "BORRAR").

### Mejoras login ✅
JWT 256 bits / 8 h. Recordarme 15 días (`/auth/jwt-remember/login`).
Google OAuth2 (`flow=login|register`): `OAuthCallbackPage`, manejo `ReadTimeout`.

### Registro multi-paso ✅
3 pasos OTP email: `send-otp` → `verify-otp` → `complete`.
Google flow=register: `complete-google`.
Campos perfil: `first_name`, `last_name`, `birth_date`, `gender`.
Campanilla "Faltan datos" en navbar.
Migración `159b99c22872`: `email_otp` + columnas perfil.

### Fase 9 ✅ — Calendario + Potencia + TSS/IF
`services/power_estimation.py`: estimación física (gravedad + aerodinámica + rodadura).
`normalized_power` en activities, `ftp`+`weight_kg` en users (migración `fa3c8e7b1d2a`).
`GET /stats/calendar-detail`: actividades/día + resúmenes semanales (dist, tiempo, cal, TSS, IF).
`POST /stats/recalculate-np`, `PATCH /users/me/training`.
CalendarPage (`/calendar`): cuadrícula semanas + totales semanales + resumen anual.

### Integración Strava ✅ (214 tests)
`StravaToken` model (migración `fb9a4f2c9133`): access_token, refresh_token, expires_at, athlete_id, last_import_at.
`services/strava_service.py`: OAuth2, retry 429 (Retry-After, máx 15 s), `strava_to_parsed()` → ParsedFit.
`routers/strava.py`:
- `GET /strava/authorize` → JSON `{authorization_url}`; state JWT con user_id firmado
- `GET /strava/callback` → sin auth; decodifica state JWT; guarda tokens; redirect frontend
- `GET /strava/status`, `DELETE /strava/disconnect`
- `POST /strava/import` → background task `_import_bg`; 1.2 s entre actividades
Frontend: `lib/strava.ts`, sección Strava en AccountPage (spinner polling 10 s hasta `last_import_at` cambia).
`docker-compose.yml`: vars `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`.
`.env.example`: documentación variables Strava.

## Bugs conocidos / pendiente inmediato

- **Strava import: datetimes timezone** — `strava_to_parsed()` devolvía datetimes con `tzinfo=UTC`; corregido con `_naive_utc()` pero la importación actual puede estar en curso con error. Relanzar desde AccountPage.
- **Strava rate limit 429** — Strava permite 600 req/15 min. Con 3 req/actividad y sleep 1.2 s entre actividades, importaciones grandes pueden saturarlo. El retry espera máx 15 s; si el límite no se recupera, hay que esperar ~15 min y reintentar.
- **114 actividades FIT con `name IS NULL`** → ejecutar `docker compose exec api python enrich_names.py --all-users`
- **`httpx-oauth` requiere reinstalación manual** tras cada rebuild: `docker compose exec api uv pip install --python /opt/venv "httpx-oauth>=0.15"`
- **Strava callback requiere JWT válido en el navegador** — si el token expira durante el flujo OAuth, el callback falla (el state JWT del backend es válido pero el usuario necesita estar autenticado para que el callback procese correctamente... en realidad NO, el callback no requiere auth, solo el state JWT). OK.

## Regla de calidad
**No cerrar una fase sin que `docker compose exec api pytest` pase al 100%.**
