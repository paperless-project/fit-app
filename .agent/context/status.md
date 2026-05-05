# Estado actual y trabajo pendiente

_Última actualización: 2026-05-05_

## Fase 1 — Completa ✅
- [x] Stack Docker: db, api, web, adminer, mailpit
- [x] BD: PostgreSQL + PostGIS, schema completo (`users`, `activities`, `laps`, `records`)
- [x] Migración Alembic aplicada (rev `379c3241c147`)
- [x] Auth completa: register, login, logout, `/users/me`, PATCH `/users/me`, verify email
- [x] Email de verificación al registrarse (Mailpit en dev → `http://localhost:8026`)
- [x] Frontend: LoginPage, RegisterPage, VerifyPage, PrivateRoute, Layout, authStore
- [x] Tests: 35 pasando (smoke, auth, activities, stats, users, verification)

## Esqueletos (código presente, sin implementación real)
- [ ] `GET /activities/` → devuelve `[]`
- [ ] `GET /stats/summary` → devuelve ceros
- [ ] `fit_parser.parse_fit()` → solo calcula hash, no extrae datos FIT
- [ ] `scripts/bulk_import.py` → itera ficheros, no persiste
- [ ] `ActivitiesPage` → placeholder "Próximamente"

## Próximos pasos (Fase 2)
1. `fit_parser.py` real — extraer session/records/laps con `fitparse`
2. `POST /activities/upload` — multipart, parsear, persistir con dedupe `(user_id, file_hash)`
3. `scripts/bulk_import.py` — completar con persistencia real
4. Tests de upload (con fichero .fit real de `/workspace/xabi/Activities/`)
5. (Fase 3) Listado de actividades en frontend

## Regla de calidad
**No cerrar una fase sin que `docker compose exec api pytest` pase al 100%.**
