# Estado actual y trabajo pendiente

_Última actualización: 2026-05-05_

## Qué funciona
- [x] Stack Docker completo arranca con `docker compose up --build`
- [x] PostgreSQL + PostGIS con schema completo (`users`, `activities`, `laps`, `records`)
- [x] Migración Alembic inicial aplicada (rev `379c3241c147`)
- [x] FastAPI con auth registrada (`/auth/register`, `/auth/jwt/login`, `/users/me`)
- [x] Vite frontend arranca, consulta `/health`, muestra estado
- [x] Adminer en `:8080` para inspección de BD
- [x] Git + GitHub (`git@github.com:paperless-project/fit-app.git`, rama `main`)

## Esqueletos (código presente pero sin implementación real)
- [ ] `GET /activities/` → devuelve `[]`
- [ ] `GET /stats/summary` → devuelve ceros
- [ ] `fit_parser.parse_fit()` → solo calcula hash, no extrae datos FIT
- [ ] `scripts/bulk_import.py` → itera ficheros, no persiste
- [ ] Frontend → sin login, sin listado, sin gráficas

## Bugs conocidos
- Los smoke tests (`tests/test_smoke.py`) fallan en entorno sin BD porque `conftest.py` usa ASGI transport pero la app intenta conectar a Postgres al importar. Pendiente aislar con un Postgres de test o mockear la sesión.
- Alembic `autogenerate` aún muestra logs de secuencias PostGIS/Tiger (solo informativo, no afecta).

## Próximos pasos por orden
1. **Fase 1** — Auth frontend: página `/login`, `useAuth` hook, guard de rutas
2. **Fase 2** — `fit_parser.py` real: extraer session/records/laps con `fitparse`
3. **Fase 2** — `POST /activities/upload`: multipart, parsear, persistir con dedupe
4. **Fase 2** — Completar `bulk_import.py`
5. **Fase 3** — Listado de actividades (tabla + filtros + paginación)
6. **Fase 4** — Detalle de actividad (mapa Leaflet + gráficas Chart.js)
7. **Fase 5** — Estadísticas agregadas (heatmap, evolución mensual)
8. **Fix tests** — BD de test en Docker para pytest

## Referencia de fases completa
Ver `doc/PLAN.md` §6.
