# Estado actual y trabajo pendiente

_Última actualización: 2026-05-06_

## Fase 1 — Auth ✅ (35 tests)
- Stack Docker, BD schema, Alembic rev `379c3241c147`
- Auth completa: register, login, logout, verify email, `/users/me`, PATCH
- Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore (Zustand)

## Fase 2 — Parser FIT + Upload ✅ (+23 tests)
- `parse_fit()`: session/records/laps, semicírculos→grados, WKT geography
- `parse_fit_safe()`: repair-with-fallback, preserva hash original para dedupe
- `fit_repair.py`: CRC-16 + trim progresivo 8192 bytes (inspirado en choochoo)
- `POST /activities/upload`: multipart, dedupe `(user_id, file_hash)`, 409/400
- `GET /activities/`: lista autenticada
- `scripts/bulk_import.py`: 114/114 ficheros importados sin errores

## Fase 3 — Listado frontend + nombres ✅ (+5 tests geocoding)
- `services/geocoding.py`: Nominatim OSM, rate-limit 1 req/s, caché ~1km
- Nombres tipo Wikiloc: "POI1, POI2 y POI3 desde StartLocality"
- Columna `name` en `activities` (migración `6bf7f63a1065`)
- `ActivitiesPage`: tabla, modal upload drag-and-drop, filas clicables

## Fase 4 — Detalle de actividad ✅ (+5 tests)
- `GET /activities/{id}`: activity + records (lat/lon via ST_AsGeoJSON) + laps
- `ActivityDetailPage`: stats, mapa Leaflet, gráficas Chart.js, tabla vueltas
- Crosshair sincronizado entre gráficas y mapa (hoverIdx compartido)

**Total: 77 tests pasando.**

## Fase 5 — Stats/dashboard (pendiente)
- `GET /stats/summary`: total km, horas, actividades, desnivel
- `GET /stats/calendar?year=YYYY`: datos para heatmap tipo GitHub
- `GET /stats/timeline?bucket=month`: evolución mensual
- Frontend: página Stats con heatmap + gráficos tendencia

## Bugs conocidos
- Nombres NULL en las 114 actividades importadas en bulk (geocoding tarda ~8 min a 1 req/s; pendiente job de enriquecimiento separado)
- `apps/api/bulk_import.py` fichero huérfano (copia temporal del contenedor)
- JWT_SECRET dev es 30 bytes (warning); producción necesita ≥32
- Sin paginación en `GET /activities/`

## Regla de calidad
**No cerrar una fase sin que `docker compose exec api pytest` pase al 100%.**
