# Base de datos

## Conexión
- Imagen: `postgis/postgis:16-3.4`
- `async_database_url`: `postgresql+asyncpg://fitapp:fitapp@db:5432/fitapp`
- `sync_database_url`: `postgresql+psycopg://...` (usado solo por Alembic)

## Tablas de la app
```
users          — fastapi-users: id(uuid), email, hashed_password, is_active, is_superuser, is_verified
activities     — id, user_id(fk), file_hash, file_name, sport, started_at, duration_s, moving_time_s,
                 distance_m, ascent_m, descent_m, avg_speed_mps, max_speed_mps, avg_hr, max_hr,
                 avg_cadence, avg_power, calories, start_point(geography), bbox(geography),
                 summary(jsonb), created_at
records        — activity_id(fk), ts → PK compuesta; position(geography), altitude_m, distance_m,
                 speed_mps, heart_rate, cadence, power, temperature
laps           — id, activity_id(fk), lap_index, start_time, duration_s, distance_m,
                 avg_speed_mps, avg_hr, ascent_m
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

## Gotchas Alembic / GeoAlchemy2
- `spatial_index=False` en TODOS los `Geography(...)` de los modelos o Alembic falla con "index already exists"
- `include_object` en `alembic/env.py` excluye tablas PostGIS/Tiger del autogenerate
- Extensiones (`uuid-ossp`, `postgis`, `citext`) se crean en la primera migración con `op.execute()`
- Nunca `Base.metadata.create_all()` — siempre `alembic upgrade head`

## Flujo de migración
```bash
# Tras tocar models/
docker compose exec api alembic revision --autogenerate -m "descripcion"
# Revisar el fichero generado ANTES de aplicar
docker compose exec api alembic upgrade head
```
