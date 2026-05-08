"""Endpoints de integración con Strava."""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.config import settings
from fitapp.db import get_session
from fitapp.models.user import StravaToken, User
from fitapp.models.activity import Activity
from fitapp.services import strava_service as ss
from fitapp.services.activity_service import _enrich_name_bg, enrich_activity_with_streams, persist_activity
from fitapp.services.strava_service import StravaRateLimitError

router = APIRouter(prefix="/strava", tags=["strava"])

_STATE_AUDIENCE = "strava-oauth"
_STATE_ALGORITHM = "HS256"


def _encode_state(user_id: uuid.UUID) -> str:
    return jwt.encode(
        {"sub": str(user_id), "aud": _STATE_AUDIENCE},
        settings.jwt_secret,
        algorithm=_STATE_ALGORITHM,
    )


def _decode_state(state: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret,
            algorithms=[_STATE_ALGORITHM],
            audience=_STATE_AUDIENCE,
        )
        return uuid.UUID(payload["sub"])
    except Exception:
        return None


@router.get("/authorize")
async def strava_authorize(user: User = Depends(current_active_user)) -> JSONResponse:
    """Devuelve la URL de autorización de Strava. El state contiene el user_id firmado."""
    state = _encode_state(user.id)
    url = ss.get_authorization_url(state)
    return JSONResponse({"authorization_url": url})


@router.get("/callback")
async def strava_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Callback de Strava. No requiere auth — el user_id viaja en el state JWT."""
    if error:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error={error}")

    if not code or not state:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error=missing_params")

    user_id = _decode_state(state)
    if user_id is None:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error=invalid_state")

    try:
        data = await ss.exchange_code(code)
    except Exception:
        return RedirectResponse(f"{settings.frontend_url}/account?strava_error=exchange_failed")

    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user_id))
    token_row = result.scalar_one_or_none()

    athlete = data.get("athlete") or {}
    if token_row is None:
        token_row = StravaToken(
            user_id=user_id,
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
    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if token_row is None:
        return {"connected": False}
    return {
        "connected": True,
        "athlete_id": token_row.athlete_id,
        "last_import_at": token_row.last_import_at,
        "import_status": token_row.import_status,
        "import_status_message": token_row.import_status_message,
    }


@router.delete("/disconnect", status_code=204)
async def strava_disconnect(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()
    if token_row:
        await db.delete(token_row)
        await db.commit()


@router.post("/import")
async def strava_import(
    background_tasks: BackgroundTasks,
    after: int | None = Query(None),
    before: int | None = Query(None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(StravaToken).where(StravaToken.user_id == user.id))
    token_row = result.scalar_one_or_none()

    if token_row and token_row.import_status == "running":
        raise HTTPException(status_code=409, detail="IMPORT_ALREADY_RUNNING")

    access_token = await ss.get_valid_access_token(db, user.id)
    background_tasks.add_task(_import_bg, str(user.id), access_token, after, before)
    return {"status": "import_started"}


# ── Helpers de la tarea de fondo ──────────────────────────────────────────────

async def _set_import_status(user_id: uuid.UUID, status: str, message: str | None) -> None:
    from fitapp.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db_bg:
        result = await db_bg.execute(select(StravaToken).where(StravaToken.user_id == user_id))
        token_row = result.scalar_one_or_none()
        if token_row:
            token_row.import_status = status
            token_row.import_status_message = message
            await db_bg.commit()


async def _call_strava(coro_fn: Callable, user_id: uuid.UUID):
    """Ejecuta una llamada a Strava gestionando rate limits.

    Ante un 429 de ventana de 15 min: actualiza estado, espera Retry-After y reintenta una vez.
    Ante un 429 diario o reintento fallido: actualiza estado y devuelve None (señal de abortar).
    """
    try:
        return await coro_fn()
    except StravaRateLimitError as e:
        if e.is_daily:
            await _set_import_status(
                user_id, "daily_limit",
                "Límite diario de Strava alcanzado. Inténtalo mañana.",
            )
            return None
        # Límite de ventana de 15 min: esperar y reintentar
        wait_min = math.ceil(e.retry_after / 60)
        await _set_import_status(
            user_id, "rate_limited",
            f"Límite de 15 min alcanzado. Reanudando en {wait_min} min…",
        )
        logger.warning("Strava rate limited for user %s — waiting %ds", user_id, e.retry_after)
        await asyncio.sleep(e.retry_after)
        await _set_import_status(user_id, "running", None)
        # Un único reintento tras la espera
        try:
            return await coro_fn()
        except StravaRateLimitError:
            await _set_import_status(
                user_id, "error",
                "Límite de Strava persistente. Inténtalo más tarde.",
            )
            return None


async def _import_bg(
    user_id_str: str,
    access_token: str,
    after: int | None,
    before: int | None,
) -> None:
    """Importación bifásica:
    Fase 1 — summaries rápidos (sin streams ni laps): persiste todas las actividades al instante.
    Fase 2 — streams en background: itera las que tienen streams_fetched=False y las enriquece.
    """
    from fitapp.db import AsyncSessionLocal

    user_id = uuid.UUID(user_id_str)
    page = 1
    imported = 0
    skipped = 0
    errors = 0
    enrich_tasks: set[asyncio.Task] = set()
    new_activity_ids: list[uuid.UUID] = []

    await _set_import_status(user_id, "running", None)
    logger.info("Strava import phase 1 started for user %s", user_id_str)

    # ── Fase 1: summaries ─────────────────────────────────────────────────────
    try:
        while True:
            activities = await _call_strava(
                lambda p=page: ss.list_activities(access_token, after=after, before=before, page=p),
                user_id,
            )
            if activities is None:
                return
            if not activities:
                break

            logger.info("Strava phase 1 page %d: %d activities", page, len(activities))

            for act in activities:
                strava_id = act["id"]
                try:
                    parsed = ss.strava_to_parsed(act, {}, [])
                    async with AsyncSessionLocal() as db_bg:
                        activity, is_dup = await persist_activity(
                            db_bg, user_id, parsed, streams_fetched=False
                        )
                    if is_dup:
                        skipped += 1
                    else:
                        imported += 1
                        new_activity_ids.append(activity.id)
                        if not activity.name:
                            t = asyncio.create_task(_enrich_name_bg(activity.id))
                            enrich_tasks.add(t)
                            t.add_done_callback(enrich_tasks.discard)
                except Exception:
                    logger.exception("Error importing Strava summary %s", strava_id)
                    errors += 1

            page += 1

    except Exception:
        logger.exception("Fatal error in Strava import phase 1")
        await _set_import_status(user_id, "error", "Error inesperado durante la importación.")
        return

    logger.info(
        "Strava phase 1 done for user %s: %d imported, %d skipped, %d errors",
        user_id_str, imported, skipped, errors,
    )

    # Actualizar estado intermedio: las actividades ya son visibles
    await _set_import_status(
        user_id, "fetching_streams",
        f"{imported} nueva{'s' if imported != 1 else ''} — descargando GPS…",
    )

    # ── Fase 2: streams y laps ────────────────────────────────────────────────
    logger.info("Strava import phase 2 (streams) started for user %s", user_id_str)
    stream_errors = 0

    try:
        async with AsyncSessionLocal() as db_bg:
            result = await db_bg.execute(
                select(Activity).where(
                    Activity.user_id == user_id,
                    Activity.streams_fetched.is_(False),
                    Activity.file_name.like("strava_%"),
                )
            )
            pending = result.scalars().all()

        logger.info("Strava phase 2: %d activities need streams", len(pending))

        for activity in pending:
            strava_id_str = activity.file_name.removeprefix("strava_").removesuffix(".json")
            try:
                strava_id = int(strava_id_str)
            except ValueError:
                continue

            try:
                streams = await _call_strava(
                    lambda sid=strava_id: ss.get_activity_streams(access_token, sid),
                    user_id,
                )
                if streams is None:
                    return

                laps_data = await _call_strava(
                    lambda sid=strava_id: ss.get_activity_laps(access_token, sid),
                    user_id,
                )
                if laps_data is None:
                    return

                async with AsyncSessionLocal() as db_bg:
                    result = await db_bg.execute(
                        select(Activity).where(Activity.id == activity.id)
                    )
                    act_row = result.scalar_one_or_none()
                    if act_row and not act_row.streams_fetched:
                        await enrich_activity_with_streams(db_bg, act_row, streams, laps_data)

            except Exception:
                logger.exception("Error fetching streams for Strava activity %s", strava_id)
                stream_errors += 1

    except Exception:
        logger.exception("Fatal error in Strava import phase 2")
        await _set_import_status(user_id, "error", "Error descargando GPS. Las actividades ya están disponibles.")
        return

    logger.info(
        "Strava import finished for user %s: %d imported, %d skipped, %d errors, %d stream_errors",
        user_id_str, imported, skipped, errors, stream_errors,
    )

    async with AsyncSessionLocal() as db_bg:
        result = await db_bg.execute(select(StravaToken).where(StravaToken.user_id == user_id))
        token_row = result.scalar_one_or_none()
        if token_row:
            token_row.last_import_at = datetime.now(timezone.utc).replace(tzinfo=None)
            token_row.import_status = "completed"
            token_row.import_status_message = (
                f"{imported} nueva{'s' if imported != 1 else ''}, "
                f"{skipped} ya existente{'s' if skipped != 1 else ''}"
            )
            await db_bg.commit()
