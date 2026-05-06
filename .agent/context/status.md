# Estado actual y trabajo pendiente

_Última actualización: 2026-05-06_

## Fase 1 ✅ — Auth (35 tests)
- Docker stack, schema BD, migración `379c3241c147`
- Auth completa: register, login, logout, verify email, `/users/me`, PATCH
- Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore (Zustand)

## Fase 2 ✅ — Parser FIT + Upload (+23 tests)
- `parse_fit()` + `parse_fit_safe()` + `fit_repair.py` (CRC-16 + trim progresivo 8192 bytes)
- `POST /activities/upload`: multipart, dedupe `(user_id, file_hash)`, 409/400
- `GET /activities/`: lista autenticada por usuario
- `bulk_import.py`: 114/114 ficheros importados sin errores

## Fase 3 ✅ — Listado frontend + nombres (+5 tests geocoding)
- `geocoding.py`: Nominatim OSM, rate-limit 1 req/s, caché ~1km
- Columna `name` en `activities` (migración `6bf7f63a1065`)
- `ActivitiesPage`: tabla, modal upload drag-and-drop, filas clicables

## Fase 4 ✅ — Detalle de actividad (+5 tests)
- `GET /activities/{id}`: activity + records (lat/lon via ST_AsGeoJSON) + laps
- `ActivityDetailPage`: stats, mapa Leaflet, gráficas Chart.js sincronizadas, tabla vueltas
- Crosshair sincronizado entre gráficas y mapa (hoverIdx compartido)

## Fase 5 ✅ — Dashboard estadísticas (+12 tests)
- `GET /stats/summary`, `GET /stats/calendar?year=`, `GET /stats/timeline?bucket=month|year`
- `StatsPage`: tarjetas resumen, heatmap estilo GitHub, gráfica de barras mensual

## Fase 6 ✅ — Filtros, edición, exportación (+23 tests)
- Filtros en `GET /activities/`: `q`, `sport`, `date_from`, `date_to`
- `PATCH /activities/{id}`: `name`, `sport`, `notes` (migración `472807ab1cee`)
- `GET /activities/export/csv`, `GET /activities/{id}/export/gpx`
- Frontend: FilterBar, botón CSV, EditModal, botón GPX

## Fase 7 ✅ — Enriquecimiento asíncrono de nombres (+10 tests)
- Geocoding asíncrono post-upload via `BackgroundTasks`
- `enrich_activity_name(db, id, force)` + `_enrich_name_bg(id)`
- `POST /activities/enrich-names`: encola actividades con `name IS NULL`
- `enrich_names.py`: CLI bulk `--all-users` / `--user-email EMAIL [--force]`
- Mock `_enrich_name_bg` en conftest apunta a `fitapp.routers.activities` (no al módulo de definición)

**Total: 119 tests pasando.**

## Bugs conocidos / pendiente
- 114 actividades bulk con `name IS NULL` → ejecutar `python enrich_names.py --all-users` en el contenedor
- `apps/api/bulk_import.py` huérfano (copia temporal); se puede borrar
- `JWT_SECRET` dev 30 bytes → warning inofensivo en dev
- Sin paginación en `GET /activities/`

## Regla de calidad
**No cerrar una fase sin que `docker compose exec api pytest` pase al 100%.**
