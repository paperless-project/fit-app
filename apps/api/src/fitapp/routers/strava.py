"""Endpoints de integración con Strava."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import current_active_user
from fitapp.config import settings
from fitapp.db import get_session
from fitapp.models.user import StravaToken, User
from fitapp.services import strava_service as ss
from fitapp.services.activity_service import _enrich_name_bg, persist_activity

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
    after: int | None = Query(None, description="Timestamp Unix: importar actividades después de esta fecha"),
    before: int | None = Query(None, description="Timestamp Unix: importar actividades antes de esta fecha"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session),
):
    access_token = await ss.get_valid_access_token(db, user.id)
    background_tasks.add_task(_import_bg, str(user.id), access_token, after, before)
    return {"status": "import_started"}


async def _import_bg(
    user_id_str: str,
    access_token: str,
    after: int | None,
    before: int | None,
) -> None:
    from fitapp.db import AsyncSessionLocal

    user_id = uuid.UUID(user_id_str)
    page = 1
    imported = 0
    skipped = 0
    errors = 0

    logger.info("Strava import started for user %s", user_id_str)

    try:
        while True:
            activities = await ss.list_activities(access_token, after=after, before=before, page=page)
            if not activities:
                break

            logger.info("Strava page %d: %d activities", page, len(activities))

            for act in activities:
                strava_id = act["id"]
                try:
                    streams = await ss.get_activity_streams(access_token, strava_id)
                    laps_data = await ss.get_activity_laps(access_token, strava_id)
                    parsed = ss.strava_to_parsed(act, streams, laps_data)

                    async with AsyncSessionLocal() as db_bg:
                        activity, is_dup = await persist_activity(db_bg, user_id, parsed)
                        await db_bg.commit()

                    if is_dup:
                        skipped += 1
                    else:
                        imported += 1
                        asyncio.create_task(_enrich_name_bg(str(activity.id)))

                    await asyncio.sleep(1.2)

                except Exception:
                    logger.exception("Error importing Strava activity %s", strava_id)
                    errors += 1

            page += 1

    except Exception:
        logger.exception("Fatal error in Strava import background task")

    logger.info(
        "Strava import finished for user %s: %d imported, %d skipped, %d errors",
        user_id_str, imported, skipped, errors,
    )

    async with AsyncSessionLocal() as db_bg:
        result = await db_bg.execute(select(StravaToken).where(StravaToken.user_id == user_id))
        token_row = result.scalar_one_or_none()
        if token_row:
            token_row.last_import_at = datetime.utcnow()
            await db_bg.commit()
