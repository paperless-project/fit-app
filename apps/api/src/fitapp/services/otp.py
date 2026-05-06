"""Servicio de generación y verificación de OTPs."""
from __future__ import annotations

import datetime
import random

import jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.config import settings
from fitapp.models.email_otp import EmailOTP

_OTP_EXPIRY_MINUTES = 10
_VERIFIED_TOKEN_MINUTES = 30
_GOOGLE_REG_TOKEN_MINUTES = 30


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


async def create_otp(db: AsyncSession, email: str) -> str:
    """Genera y persiste un OTP. Invalida los anteriores del mismo email."""
    await db.execute(delete(EmailOTP).where(EmailOTP.email == email))
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=_OTP_EXPIRY_MINUTES
    )
    code = _generate_code()
    db.add(EmailOTP(email=email, code=code, expires_at=expires_at))
    await db.commit()
    return code


async def verify_otp(db: AsyncSession, email: str, code: str) -> bool:
    """Verifica el OTP. Devuelve True si es válido y lo marca como usado."""
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await db.execute(
        select(EmailOTP).where(
            EmailOTP.email == email,
            EmailOTP.code == code,
            EmailOTP.used.is_(False),
            EmailOTP.expires_at > now,
        )
    )
    otp = result.scalar_one_or_none()
    if otp is None:
        return False
    otp.used = True
    await db.commit()
    return True


def create_verified_token(email: str) -> str:
    """JWT de corta duración que certifica que el email fue verificado por OTP."""
    payload = {
        "sub": email,
        "type": "otp_verified",
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=_VERIFIED_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_verified_token(token: str) -> str | None:
    """Decodifica el verified_token. Devuelve el email o None si es inválido/expirado."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "otp_verified":
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def create_google_registration_token(
    *,
    email: str,
    first_name: str,
    last_name: str,
    account_id: str,
    google_access_token: str,
    expires_at: int | None,
    refresh_token: str | None,
) -> str:
    """JWT que certifica que el email fue verificado por Google y contiene los datos OAuth."""
    payload = {
        "sub": email,
        "type": "google_registration",
        "first_name": first_name,
        "last_name": last_name,
        "account_id": account_id,
        "google_access_token": google_access_token,
        "expires_at": expires_at,
        "refresh_token": refresh_token,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=_GOOGLE_REG_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_google_registration_token(token: str) -> dict | None:
    """Decodifica el google_registration_token. Devuelve el payload o None si es inválido."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "google_registration":
            return None
        return payload
    except jwt.PyJWTError:
        return None
