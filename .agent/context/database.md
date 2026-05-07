# Base de datos

## Conexión
- Imagen: `postgis/postgis:16-3.4`
- `async_database_url`: `postgresql+asyncpg://fitapp:fitapp@db:5432/fitapp`
- `sync_database_url`: `postgresql+psycopg://...` (solo Alembic)

## Tablas de la app
```
users          id(uuid PK), email(citext UNIQUE), hashed_password,
               is_active, is_superuser, is_verified,
               first_name, last_name, birth_date, gender(gender_enum),
               ftp(int), weight_kg(numeric 5,2)

oauth_account  id(uuid PK), oauth_name, access_token, account_id, account_email,
               user_id(FK→users CASCADE)
               ⚠ FK debe apuntar a "users.id" — sobreescribir con @declared_attr

email_otp      id(uuid PK), email, code(6 dígitos), expires_at, used(bool)

strava_tokens  user_id(uuid PK FK→users CASCADE),
               access_token(varchar 255), refresh_token(varchar 255),
               expires_at(bigint epoch Unix), athlete_id(bigint NULL),
               last_import_at(timestamp NULL)

activities     id(uuid PK), user_id(FK→users CASCADE),
               file_hash(text), file_name(text),  ← strava: "strava_{id}.json"
               name(varchar 255 NULL), notes(text NULL), sport,
               started_at(TIMESTAMP — naive UTC), duration_s, moving_time_s,
               distance_m, ascent_m, descent_m, avg_speed_mps, max_speed_mps,
               avg_hr, max_hr, avg_cadence, avg_power, normalized_power, calories,
               start_point(geography POINT), bbox(geography POLYGON)
               UNIQUE(user_id, file_hash)

records        activity_id(FK→activities CASCADE), ts(TIMESTAMP — naive UTC) → PK compuesta
               position(geography POINT NULL), altitude_m, distance_m, speed_mps,
               heart_rate, cadence, power, temperature

laps           id(uuid PK), activity_id(FK→activities CASCADE), lap_index,
               start_time(TIMESTAMP), duration_s, distance_m, avg_speed_mps, avg_hr, ascent_m
               UNIQUE(activity_id, lap_index)
```

## Migraciones Alembic (en orden)
```
379c3241c147  initial_schema                   — tablas, extensiones, índices GiST
6bf7f63a1065  add_activity_name                — activities.name
472807ab1cee  add_notes_to_activities          — activities.notes
5a37abab0ca1  add_oauth_account_table          — tabla OAuth Google
159b99c22872  add_email_otp_and_profile_fields — email_otp + first_name/last_name/birth_date/gender
fa3c8e7b1d2a  add_normalized_power_ftp_weight  — activities.normalized_power + users.ftp/weight_kg
fb9a4f2c9133  add_strava_tokens                — tabla strava_tokens
```

## Gotchas críticos
- `spatial_index=False` en TODOS los `Geography(...)` — evita colisión con índices Alembic
- `include_object` en `alembic/env.py` excluye tablas PostGIS/Tiger
- **Autogenerate detecta falsos positivos de índices GiST** — eliminar siempre del fichero generado
- `ST_X/ST_Y` fallan sobre `geography` → usar `ST_AsGeoJSON` + `json.loads()`
- Columnas `TIMESTAMP WITHOUT TIME ZONE` — insertar datetimes **naive** (sin tzinfo). Strava devuelve ISO con Z → convertir con `_naive_utc()`
- Nunca `Base.metadata.create_all()` — siempre `alembic upgrade head`
- Tests usan `NullPool` — sin reutilización de conexiones entre tests

## Deduplicación actividades
- FIT: `file_hash = sha256(fichero_original)`
- Strava: `file_hash = sha256("strava-{strava_id}")` — prefijo evita colisión con FIT

## Flujo de migración
```bash
docker compose exec api alembic revision --autogenerate -m "descripcion"
# ⚠️ Revisar fichero: eliminar drop_index de índices GiST (falsos positivos)
docker compose exec api alembic upgrade head
```
