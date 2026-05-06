# Arquitectura

## Estructura del repo
```
fit-app/
├── apps/api/          Python/FastAPI
│   ├── src/fitapp/
│   │   ├── auth/      users.py (fastapi-users config)
│   │   ├── models/    activity.py, user.py (SQLAlchemy 2.0)
│   │   ├── routers/   activities.py, stats.py
│   │   ├── schemas/   activity.py, stats.py
│   │   ├── services/  activity_service.py, fit_parser.py, fit_repair.py, geocoding.py, email.py
│   │   ├── config.py  settings (pydantic-settings)
│   │   ├── db.py      engine, SessionLocal, get_session
│   │   └── main.py    FastAPI app, routers incluidos
│   ├── alembic/       migraciones
│   ├── tests/         pytest suite
│   ├── bulk_import.py CLI importación masiva
│   └── enrich_names.py CLI enriquecimiento nombres
├── apps/web/          React/Vite
│   └── src/{components,pages,lib,store,types}
└── scripts/           bulk_import.py original
```

## Flujo principal: upload
```
POST /activities/upload (multipart .fit)
  → parse_fit_safe()
      → parse_fit()           OK → ParsedFit
      → fit_repair() si falla → parse_fit() reparado
  → persist_activity()
      → dedupe (user_id, file_hash) → 409 si existe
      → INSERT activity (name=NULL) + records + laps
      → COMMIT
  → background_tasks.add_task(_enrich_name_bg, activity.id)
  → 201 ActivityOut (inmediato, sin esperar geocoding)

_enrich_name_bg(id) [background, sesión propia]
  → enrich_activity_name(db, id)
      → SELECT records con posición
      → generate_activity_name(records) → Nominatim → str|None
      → UPDATE activities.name si result
```

## Flujo geocoding
```
generate_activity_name(records):
  1. _reverse(start, zoom=13)  → start_locality
  2. _reverse(gps[95%], zoom=13) → end_locality
  3. haversine(start, end) ≤ 1.5km → is_loop
  4. Para frac in (0.15, 0.30, 0.50, 0.70, 0.85):
       _reverse(gps[frac*n], zoom=17) → POI notable (max 3)
  5. Bucle:   "POI1, POI2 y POI3 desde StartLocality"
     P2P:     "De StartLocality a EndLocality vía POI1"
```

## Flujo auth + verificación email
```
POST /auth/register → on_after_register → request_verify
                    → send_verification_email(email, token) → SMTP → Mailpit (dev)
/verify?token=TOKEN → POST /auth/verify → is_verified=True
```

## Multi-tenant
- `user_id FK → users(id) ON DELETE CASCADE` en activities/records/laps
- `UNIQUE(user_id, file_hash)` en activities
- Todos los endpoints filtran por `current_active_user` del JWT

## Decisiones irreversibles
- Parsing en **backend**
- **PostgreSQL** + PostGIS (geography, ST_AsGeoJSON)
- **`fastapi-users`** para auth
- Geocoding via **Nominatim** (OSM, sin API key)
- FIT repair en **Python puro**
- Geocoding **asíncrono** (BackgroundTasks), no bloqueante en upload
