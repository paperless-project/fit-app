# Importar actividades desde Strava

Implementa la integración con la API de Strava para importar actividades del usuario directamente desde Strava, sin necesidad de ficheros FIT.

## Alcance

### Backend (FastAPI)
1. **Modelo `StravaToken`** — almacena tokens OAuth2 por usuario
2. **Migración Alembic** — tabla `strava_tokens`
3. **Config** — nuevas vars `strava_client_id`, `strava_client_secret`
4. **`services/strava_service.py`** — cliente HTTP + conversión de datos
5. **`routers/strava.py`** — 6 endpoints
6. **Tests pytest**

### Frontend (React + TypeScript)
1. **Sección Strava en `AccountPage`** — conectar/desconectar + botón importar
2. **`lib/strava.ts`** — funciones de API del frontend
3. **`types/strava.ts`** — tipos TypeScript

---

## 1. Configuración y variables de entorno

### `apps/api/src/fitapp/config.py`
Añadir al modelo `Settings`:
```python
strava_client_id: str = ""
strava_client_secret: str = ""
```

### `apps/api/.env` (o `.env.example`)
```
STRAVA_CLIENT_ID=tu_client_id
STRAVA_CLIENT_SECRET=tu_client_secret
```

El `redirect_uri` se construye dinámicamente: `{settings.api_url}/strava/callback`

---

## 2. Modelo `StravaToken`

### `apps/api/src/fitapp/models/user.py`
Añadir la clase al final del fichero (no en fichero separado — el módulo de modelos ya es pequeño):

```python
class StravaToken(Base):
    __tablename__ = "strava_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    access_token: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)  # epoch Unix
    athlete_id: Mapped[int | None] = mapped_column(Integer)
    last_import_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
```

---

## 3. Migración Alembic

```bash
docker compose exec api alembic revision --autogenerate -m "add_strava_tokens"
```

Revisar el fichero generado: debe contener solo la tabla `strava_tokens`. Eliminar cualquier índice GiST falso positivo. Luego:

```bash
docker compose exec api alembic upgrade head
```

---

## 4. Servicio `strava_service.py`

Crear `apps/api/src/fitapp/services/strava_service.py`:

```python
"""Cliente Strava API + conversión de actividades a ParsedFit."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from fitapp.config import settings
from fitapp.services.fit_parser import ParsedFit

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"
SCOPE = "activity:read_all"

# Streams a solicitar (en orden; Strava acepta hasta 10)
STREAM_KEYS = "time,latlng,altitude,heartrate,cadence,watts,temp,distance,velocity_smooth"


def get_authorization_url(state: str) -> str:
    """Construye la URL de autorización OAuth de Strava."""
    redirect_uri = f"{settings.api_url}/strava/callback"
    return (
        f"{STRAVA_AUTH_URL}"
        f"?client_id={settings.strava_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&approval_prompt=auto"
        f"&scope={SCOPE}"
        f"&state={state}"
    )


async def exchange_code(code: str) -> dict:
    """Intercambia un authorization code por access_token + refresh_token."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(STRAVA_TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresca el access_token usando el refresh_token."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(STRAVA_TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()


def is_token_expired(expires_at: int) -> bool:
    """Devuelve True si el token expira en menos de 60 segundos."""
    return time.time() >= expires_at - 60


async def get_valid_access_token(db, user_id) -> str:
    """Obtiene un access token válido, refrescándolo si es necesario.

    Actualiza la BD si se refresca.
    Lanza HTTPException 401 si no hay token guardado.
    """
    from fastapi import HTTPException
    from sqlalchemy import select
    from fitapp.models.user import StravaToken

    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user_id))
    token_row = result.scalar_one_or_none()
    if token_row is None:
        raise HTTPException(status_code=401, detail="Strava no conectado")

    if is_token_expired(token_row.expires_at):
        data = await refresh_access_token(token_row.refresh_token)
        token_row.access_token = data["access_token"]
        token_row.refresh_token = data["refresh_token"]
        token_row.expires_at = data["expires_at"]
        await db.commit()

    return token_row.access_token


async def list_activities(
    access_token: str,
    after: int | None = None,
    before: int | None = None,
    page: int = 1,
    per_page: int = 100,
) -> list[dict]:
    """Devuelve actividades resumidas del atleta (máx per_page por llamada)."""
    params: dict[str, Any] = {"page": page, "per_page": per_page}
    if after:
        params["after"] = after
    if before:
        params["before"] = before

    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {access_token}"}) as client:
        r = await client.get(f"{STRAVA_API_BASE}/athlete/activities", params=params)
        r.raise_for_status()
        return r.json()


async def get_activity_streams(access_token: str, activity_id: int) -> dict[str, list]:
    """Obtiene los streams de tiempo, GPS, altitud, FC, cadencia, potencia, etc."""
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {access_token}"}) as client:
        r = await client.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
            params={"keys": STREAM_KEYS, "key_by_type": "true"},
        )
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return {k: v["data"] for k, v in r.json().items()}


async def get_activity_laps(access_token: str, activity_id: int) -> list[dict]:
    """Obtiene los laps de una actividad."""
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {access_token}"}) as client:
        r = await client.get(f"{STRAVA_API_BASE}/activities/{activity_id}/laps")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()


def strava_hash(strava_id: int) -> str:
    """Genera un file_hash reproducible para una actividad Strava.

    Usamos un prefijo 'strava-' para que no colisione con hashes de ficheros FIT.
    """
    return hashlib.sha256(f"strava-{strava_id}".encode()).hexdigest()


def strava_to_parsed(activity: dict, streams: dict, laps_data: list[dict]) -> ParsedFit:
    """Convierte una actividad Strava + streams en un ParsedFit listo para persistir."""
    strava_id = activity["id"]
    started_at_str = activity.get("start_date")  # ISO 8601 UTC
    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00")) if started_at_str else None

    # ── punto de inicio ──────────────────────────────────────────────────────
    start_latlng = activity.get("start_latlng") or []
    start_point_wkt = None
    if len(start_latlng) == 2:
        lat, lon = start_latlng
        start_point_wkt = f"POINT({lon} {lat})"

    # ── bounding box ─────────────────────────────────────────────────────────
    bbox_wkt = None
    latlng_stream = streams.get("latlng", [])
    if latlng_stream:
        lats = [p[0] for p in latlng_stream]
        lons = [p[1] for p in latlng_stream]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        bbox_wkt = (
            f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
            f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
        )

    # ── records (serie temporal) ─────────────────────────────────────────────
    records: list[dict] = []
    time_stream = streams.get("time", [])       # segundos desde started_at
    dist_stream = streams.get("distance", [])
    spd_stream = streams.get("velocity_smooth", [])
    alt_stream = streams.get("altitude", [])
    hr_stream = streams.get("heartrate", [])
    cad_stream = streams.get("cadence", [])
    pwr_stream = streams.get("watts", [])
    temp_stream = streams.get("temp", [])

    for i, t in enumerate(time_stream):
        lat, lon = (latlng_stream[i] if i < len(latlng_stream) else (None, None))
        if isinstance(lat, list):  # Strava devuelve [lat, lon]
            lat, lon = lat[0], lat[1]

        records.append({
            "ts": started_at.replace(tzinfo=timezone.utc) + __import__("datetime").timedelta(seconds=t)
                  if started_at else None,
            "lat": lat,
            "lon": lon,
            "altitude_m": alt_stream[i] if i < len(alt_stream) else None,
            "distance_m": dist_stream[i] if i < len(dist_stream) else None,
            "speed_mps": spd_stream[i] if i < len(spd_stream) else None,
            "heart_rate": int(hr_stream[i]) if i < len(hr_stream) else None,
            "cadence": int(cad_stream[i]) if i < len(cad_stream) else None,
            "power": int(pwr_stream[i]) if i < len(pwr_stream) else None,
            "temperature": int(temp_stream[i]) if i < len(temp_stream) else None,
        })

    # ── laps ─────────────────────────────────────────────────────────────────
    laps: list[dict] = []
    for i, lap in enumerate(laps_data):
        st_str = lap.get("start_date")
        st = datetime.fromisoformat(st_str.replace("Z", "+00:00")) if st_str else None
        laps.append({
            "lap_index": i,
            "start_time": st,
            "duration_s": lap.get("elapsed_time"),
            "distance_m": lap.get("distance"),
            "avg_speed_mps": lap.get("average_speed"),
            "avg_hr": lap.get("average_heartrate"),
            "ascent_m": lap.get("total_elevation_gain"),
        })

    return ParsedFit(
        file_hash=strava_hash(strava_id),
        file_name=f"strava_{strava_id}.json",
        started_at=started_at,
        sport=activity.get("sport_type") or activity.get("type"),
        duration_s=activity.get("elapsed_time"),
        moving_time_s=activity.get("moving_time"),
        distance_m=activity.get("distance"),
        ascent_m=activity.get("total_elevation_gain"),
        descent_m=None,  # Strava no lo devuelve en el summary
        avg_speed_mps=activity.get("average_speed"),
        max_speed_mps=activity.get("max_speed"),
        avg_hr=int(activity["average_heartrate"]) if activity.get("average_heartrate") else None,
        max_hr=int(activity["max_heartrate"]) if activity.get("max_heartrate") else None,
        avg_cadence=int(activity["average_cadence"]) if activity.get("average_cadence") else None,
        avg_power=int(activity["average_watts"]) if activity.get("average_watts") else None,
        calories=activity.get("calories"),
        start_point_wkt=start_point_wkt,
        bbox_wkt=bbox_wkt,
        records=records,
        laps=laps,
    )
```

**Nota crítica sobre los timestamps en `strava_to_parsed`**: la línea que construye el `ts` del record usa `datetime.timedelta` importado con `__import__`. Refactoriza para importar `timedelta` al principio del fichero junto con `datetime`:

```python
from datetime import datetime, timedelta, timezone
# ...
"ts": started_at.replace(tzinfo=timezone.utc) + timedelta(seconds=t) if started_at else None,
```

---

## 5. Router `strava.py`

Crear `apps/api/src/fitapp/routers/strava.py`:

```python
"""Endpoints de integración con Strava."""
from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.db import get_session
from fitapp.models.user import StravaToken, User
from fitapp.services import strava_service as ss
from fitapp.services.activity_service import _enrich_name_bg, persist_activity

router = APIRouter(prefix="/strava", tags=["strava"])


@router.get("/authorize")
async def strava_authorize(user: User = Depends(current_active_user)):
    """Redirige al usuario a la pantalla de autorización de Strava."""
    state = secrets.token_urlsafe(16)
    url = ss.get_authorization_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def strava_callback(
    code: str = Query(...),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    """Recibe el callback de Strava, guarda tokens y redirige al frontend."""
    from fitapp.config import settings

    if error:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error={error}")

    try:
        data = await ss.exchange_code(code)
    except Exception:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error=exchange_failed")

    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()

    athlete = data.get("athlete", {})
    if token_row is None:
        token_row = StravaToken(
            user_id=user.id,
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            athlete_id=athlete.get("id"),
        )
        db.add(token_row)
    else:
        token_row.access_token = data["access_token"]
        token_row.refresh_token = data["refresh_token"]
        token_row.expires_at = data["expires_at"]
        token_row.athlete_id = athlete.get("id")

    await db.commit()
    return RedirectResponse(f"{settings.frontend_url}/account?strava_connected=1")


@router.get("/status")
async def strava_status(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    """Devuelve si el usuario tiene Strava conectado y cuándo fue la última importación."""
    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if token_row is None:
        return {"connected": False}
    return {
        "connected": True,
        "athlete_id": token_row.athlete_id,
        "last_import_at": token_row.last_import_at,
    }


@router.delete("/disconnect", status_code=204)
async def strava_disconnect(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    """Elimina los tokens de Strava del usuario."""
    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if token_row:
        await db.delete(token_row)
        await db.commit()


@router.post("/import")
async def strava_import(
    background_tasks: BackgroundTasks,
    after: int | None = Query(None, description="Timestamp Unix: importar actividades después de esta fecha"),
    before: int | None = Query(None, description="Timestamp Unix: importar actividades antes de esta fecha"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    """Encola la importación de actividades desde Strava en segundo plano."""
    access_token = await ss.get_valid_access_token(db, user.id)
    background_tasks.add_task(_import_bg, str(user.id), access_token, after, before)
    return {"status": "import_started"}


async def _import_bg(user_id_str: str, access_token: str, after: int | None, before: int | None):
    """Tarea de fondo: importa todas las páginas de actividades de Strava."""
    import uuid
    from fitapp.db import AsyncSessionLocal

    user_id = uuid.UUID(user_id_str)
    page = 1
    imported = 0
    skipped = 0

    while True:
        activities = await ss.list_activities(access_token, after=after, before=before, page=page)
        if not activities:
            break

        for act in activities:
            strava_id = act["id"]
            try:
                streams = await ss.get_activity_streams(access_token, strava_id)
                laps_data = await ss.get_activity_laps(access_token, strava_id)
                parsed = ss.strava_to_parsed(act, streams, laps_data)

                async with AsyncSessionLocal() as db:
                    activity, is_dup = await persist_activity(db, user_id, parsed)
                    await db.commit()

                if is_dup:
                    skipped += 1
                else:
                    imported += 1
                    asyncio.create_task(_enrich_name_bg(str(activity.id)))

                # Rate limit: ~1 req/s para no saturar los 600 req/15min de Strava
                await asyncio.sleep(1.2)

            except Exception:
                pass  # No interrumpir el bulk import por un error individual

        page += 1

    # Actualizar last_import_at
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(StravaToken).where(StravaToken.user_id == user_id))
        token_row = result.scalar_one_or_none()
        if token_row:
            token_row.last_import_at = datetime.now(timezone.utc)
            await db.commit()
```

**Nota**: `AsyncSessionLocal` debe estar exportado desde `fitapp.db`. Comprueba que existe; si no, añádelo:
```python
# apps/api/src/fitapp/db.py — añadir si no existe:
from sqlalchemy.ext.asyncio import async_sessionmaker
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

---

## 6. Registrar el router en `main.py`

```python
# apps/api/src/fitapp/main.py
from fitapp.routers.strava import router as strava_router
# ...
app.include_router(strava_router)
```

Registrarlo ANTES de los routers de fastapi-users para evitar colisiones de prefijo.

---

## 7. Tests pytest

Crear `apps/api/tests/test_strava.py`:

### Tests de `strava_service.py`
- `test_strava_hash_deterministic`: el mismo `strava_id` siempre produce el mismo hash
- `test_strava_hash_no_collision`: hashes de IDs distintos no colisionan
- `test_strava_to_parsed_basic`: actividad sin streams devuelve ParsedFit con los campos básicos
- `test_strava_to_parsed_with_streams`: con streams completos, los records tienen lat/lon/hr/potencia
- `test_strava_to_parsed_no_gps`: sin `latlng` stream, `start_point_wkt` y `bbox_wkt` son None
- `test_is_token_expired_true`: token con `expires_at` en el pasado devuelve True
- `test_is_token_expired_false`: token con `expires_at` en el futuro devuelve False

### Tests de endpoints (mocks HTTP externos)
Usar `patch("fitapp.services.strava_service.exchange_code")` etc.

- `test_strava_status_not_connected`: GET /strava/status sin token → `{"connected": false}`
- `test_strava_status_connected`: GET /strava/status con token guardado → `{"connected": true, ...}`
- `test_strava_disconnect`: DELETE /strava/disconnect elimina el token de la BD
- `test_strava_callback_success`: GET /strava/callback con code válido → redirige a frontend con `strava_connected=1`
- `test_strava_callback_error`: GET /strava/callback con `error=access_denied` → redirige con `strava_error`
- `test_strava_import_no_token`: POST /strava/import sin token → 401
- `test_strava_import_enqueued`: POST /strava/import con token → 200, `{"status": "import_started"}`

### Patrón de fixture recomendado
```python
@pytest.fixture
async def strava_token(db_session, test_user):
    from fitapp.models.user import StravaToken
    token = StravaToken(
        user_id=test_user.id,
        access_token="fake_access",
        refresh_token="fake_refresh",
        expires_at=int(time.time()) + 3600,
        athlete_id=12345,
    )
    db_session.add(token)
    await db_session.commit()
    return token
```

---

## 8. Frontend: `lib/strava.ts`

Crear `apps/web/src/lib/strava.ts`:

```typescript
import { API_BASE } from "./config";  // o donde esté la base URL

export async function getStravaStatus(): Promise<{
  connected: boolean;
  athlete_id?: number;
  last_import_at?: string;
}> {
  const res = await fetch(`${API_BASE}/strava/status`, { credentials: "include" });
  if (!res.ok) throw new Error("Error al obtener estado de Strava");
  return res.json();
}

export async function disconnectStrava(): Promise<void> {
  const res = await fetch(`${API_BASE}/strava/disconnect`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Error al desconectar Strava");
}

export async function startStravaImport(after?: number, before?: number): Promise<void> {
  const params = new URLSearchParams();
  if (after) params.set("after", String(after));
  if (before) params.set("before", String(before));

  const res = await fetch(`${API_BASE}/strava/import?${params}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Error al iniciar la importación");
}

export function connectStrava(): void {
  // Redirige directamente; el backend maneja el redirect a Strava
  window.location.href = `${API_BASE}/strava/authorize`;
}
```

---

## 9. Frontend: sección Strava en `AccountPage`

Añadir una sección nueva en `apps/web/src/pages/AccountPage.tsx` (después de la sección de contraseña, antes de la zona de peligro):

```tsx
// Imports adicionales:
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { connectStrava, disconnectStrava, getStravaStatus, startStravaImport } from "../lib/strava";

// Estado local para el formulario de importación:
const [importAfter, setImportAfter] = useState("");  // fecha ISO string → convertir a epoch
const [importBefore, setImportBefore] = useState("");
const [importMsg, setImportMsg] = useState("");

const qc = useQueryClient();
const { data: stravaStatus } = useQuery({
  queryKey: ["strava-status"],
  queryFn: getStravaStatus,
});

const disconnectMutation = useMutation({
  mutationFn: disconnectStrava,
  onSuccess: () => qc.invalidateQueries({ queryKey: ["strava-status"] }),
});

const importMutation = useMutation({
  mutationFn: () => {
    const after = importAfter ? Math.floor(new Date(importAfter).getTime() / 1000) : undefined;
    const before = importBefore ? Math.floor(new Date(importBefore).getTime() / 1000) : undefined;
    return startStravaImport(after, before);
  },
  onSuccess: () => setImportMsg("Importación iniciada. Las actividades aparecerán en unos minutos."),
});
```

**JSX de la sección**:
```tsx
<section>
  <h2>Strava</h2>
  {stravaStatus?.connected ? (
    <>
      <p>Conectado (Atleta ID: {stravaStatus.athlete_id})</p>
      {stravaStatus.last_import_at && (
        <p>Última importación: {new Date(stravaStatus.last_import_at).toLocaleString()}</p>
      )}
      <div>
        <label>Desde: <input type="date" value={importAfter} onChange={e => setImportAfter(e.target.value)} /></label>
        <label>Hasta: <input type="date" value={importBefore} onChange={e => setImportBefore(e.target.value)} /></label>
        <button onClick={() => importMutation.mutate()} disabled={importMutation.isPending}>
          {importMutation.isPending ? "Importando..." : "Importar actividades"}
        </button>
        {importMsg && <p>{importMsg}</p>}
      </div>
      <button onClick={() => disconnectMutation.mutate()}>Desconectar Strava</button>
    </>
  ) : (
    <button onClick={connectStrava}>Conectar con Strava</button>
  )}
</section>
```

Gestionar también el parámetro `?strava_connected=1` y `?strava_error=...` en la URL al montar la página (similar a como se gestiona `?google_token` en `RegisterPage`).

---

## 10. Registrar app en Strava

Para que el OAuth funcione, el usuario debe crear una app en https://www.strava.com/settings/api y configurar:
- **Authorization Callback Domain**: `localhost` (en dev)
- Copiar Client ID y Client Secret al `.env`

---

## Convenciones del proyecto
- Stack: `fastapi-users`, SQLAlchemy 2.0 async, TanStack Query, Zustand, Tailwind
- Nunca `Base.metadata.create_all()` — siempre Alembic
- Nunca colisionar con tests existentes: los 187 tests actuales deben seguir pasando
- Strava tokens son secretos: nunca devolverlos en ningún endpoint de la API
- Rate limit de Strava: 600 requests/15min — usar `asyncio.sleep(1.2)` entre requests en bulk

## Orden de implementación

1. Añadir vars a `config.py` y modelo `StravaToken` a `models/user.py`
2. Generar y aplicar migración Alembic
3. Crear `services/strava_service.py`
4. Verificar que `AsyncSessionLocal` existe en `db.py`; añadirlo si no
5. Crear `routers/strava.py` y registrarlo en `main.py`
6. Escribir tests en `test_strava.py`
7. Ejecutar `docker compose exec api pytest` — todos verdes
8. Frontend: `lib/strava.ts` + sección en `AccountPage`
9. Arrancar el stack y probar el flujo completo en el navegador
10. **Una fase no se da por completada hasta que todos los tests pasen al 100%**
