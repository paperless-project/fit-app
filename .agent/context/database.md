# Base de datos

## Conexión
- Imagen: `postgis/postgis:16-3.4`
- `async_database_url`: `postgresql+asyncpg://fitapp:fitapp@db:5432/fitapp`
- `sync_database_url`: `postgresql+psycopg://...` (solo Alembic)

## Tablas de la app
```
users          id(uuid PK), email(citext UNIQUE), hashed_password,
               is_active, is_superuser, is_verified, created_at

activities     id(uuid PK), user_id(FK→users CASCADE),
               file_hash(text), file_name(text),
               name(varchar 255 NULL),
               notes(text NULL),
               sport(text), started_at(timestamptz),
               duration_s, moving_time_s, distance_m, ascent_m, descent_m,
               avg_speed_mps, max_speed_mps, avg_hr, max_hr, avg_cadence, avg_power,
               calories, start_point(geography POINT), bbox(geography POLYGON),
               created_at
               UNIQUE(user_id, file_hash)

records        activity_id(FK→activities CASCADE), ts(timestamptz) → PK compuesta
               position(geography POINT NULL), altitude_m, distance_m, speed_mps,
               heart_rate, cadence, power, temperature

laps           id(uuid PK), activity_id(FK→activities CASCADE), lap_index,
               start_time, duration_s, distance_m, avg_speed_mps, avg_hr, ascent_m
               UNIQUE(activity_id, lap_index)
```

## Migraciones Alembic
```
379c3241c147  initial_schema         — tablas, extensiones (uuid-ossp, postgis, citext), índices GiST
6bf7f63a1065  add_activity_name      — activities.name VARCHAR(255) NULL
472807ab1cee  add_notes_to_activities — activities.notes Text NULL
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
- **Autogenerate detecta falsos positivos de índices GiST** — revisar siempre el fichero antes de aplicar
- `ST_X(geography)` y `ST_Y(geography)` fallan — usar `ST_AsGeoJSON(geography)` y parsear JSON
- Extensiones en primera migración via `op.execute("CREATE EXTENSION IF NOT EXISTS ...")`
- Nunca `Base.metadata.create_all()` — siempre `alembic upgrade head`

## Flujo de migración
```bash
docker compose exec api alembic revision --autogenerate -m "descripcion"
# Revisar el fichero generado: eliminar drop_index de índices GiST (falsos positivos)
docker compose exec api alembic upgrade head
```
