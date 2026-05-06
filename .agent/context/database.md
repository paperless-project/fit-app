# Base de datos

## Conexión
- Imagen: `postgis/postgis:16-3.4`
- `async_database_url`: `postgresql+asyncpg://fitapp:fitapp@db:5432/fitapp`
- `sync_database_url`: `postgresql+psycopg://...` (solo Alembic)

## Tablas de la app
```
users          id(uuid), email(unique), hashed_password, is_active, is_superuser, is_verified
activities     id, user_id(fk→CASCADE), file_hash, file_name, name, sport, started_at,
               duration_s, moving_time_s, distance_m, ascent_m, descent_m,
               avg_speed_mps, max_speed_mps, avg_hr, max_hr, avg_cadence, avg_power,
               calories, start_point(geography POINT), bbox(geography POLYGON),
               summary(jsonb), created_at
               UNIQUE(user_id, file_hash)
records        (activity_id, ts) → PK compuesta
               position(geography POINT), altitude_m, distance_m, speed_mps,
               heart_rate, cadence, power, temperature
laps           id, activity_id(fk→CASCADE), lap_index, start_time, duration_s,
               distance_m, avg_speed_mps, avg_hr, ascent_m
               UNIQUE(activity_id, lap_index)
```

## Migraciones Alembic
```
379c3241c147  initial_schema   — tablas, extensiones, índices GiST
6bf7f63a1065  add_activity_name — columna activities.name VARCHAR(255) NULL
```

## Índices
```
ix_users_email               UNIQUE btree
uq_activities_user_hash      UNIQUE (user_id, file_hash)
idx_activities_user_started  btree (user_id, started_at)
idx_activities_start_point   GiST geography
idx_activities_bbox          GiST geography
idx_records_position         GiST geography
```

## Gotchas críticos
- `spatial_index=False` en TODOS los `Geography(...)` de modelos — evita colisión con índices Alembic
- `include_object` en `alembic/env.py` excluye tablas PostGIS/Tiger del autogenerate
- Autogenerate puede detectar falsos positivos de índices GiST — revisar siempre el fichero generado antes de aplicar
- `ST_X(geography)` y `ST_Y(geography)` fallan — usar `ST_AsGeoJSON(geography)` y parsear JSON
- Extensiones en primera migración: `uuid-ossp`, `postgis`, `citext` via `op.execute()`
- Nunca `Base.metadata.create_all()` — siempre `alembic upgrade head`

## Flujo de migración
```bash
docker compose exec api alembic revision --autogenerate -m "descripcion"
# Revisar el fichero generado (eliminar falsos positivos de índices GiST)
docker compose exec api alembic upgrade head
```
