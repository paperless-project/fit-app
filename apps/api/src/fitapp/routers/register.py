"""Router de registro multi-paso con OTP y Google."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users.exceptions import InvalidPasswordException, UserNotExists
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fitapp.auth.users import auth_backend, get_user_manager, google_oauth_client
from fitapp.db import get_session
from fitapp.models.user import User
from fitapp.schemas.register import (
    CompleteGoogleRegistrationRequest,
    CompleteGoogleRegistrationResponse,
    CompleteRegistrationRequest,
    CompleteRegistrationResponse,
    SendOTPRequest,
    SendOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from fitapp.services.email import send_otp_email, send_welcome_email
from fitapp.services.otp import (
    create_otp,
    create_verified_token,
    decode_google_registration_token,
    decode_verified_token,
    verify_otp,
)

router = APIRouter(prefix="/auth/register", tags=["register"])


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(
    body: SendOTPRequest,
    db: AsyncSession = Depends(get_session),
) -> SendOTPResponse:
    """Paso 1: genera y envía OTP al email indicado."""
    code = await create_otp(db, str(body.email))
    await send_otp_email(str(body.email), code)
    return SendOTPResponse(message="OTP enviado")


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp_endpoint(
    body: VerifyOTPRequest,
    db: AsyncSession = Depends(get_session),
) -> VerifyOTPResponse:
    """Paso 2: verifica el OTP y devuelve un verified_token."""
    valid = await verify_otp(db, str(body.email), body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código incorrecto o expirado")
    return VerifyOTPResponse(verified_token=create_verified_token(str(body.email)))


@router.post("/complete", response_model=CompleteRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def complete_registration(
    body: CompleteRegistrationRequest,
    user_manager=Depends(get_user_manager),
) -> CompleteRegistrationResponse:
    """Paso 3: crea la cuenta con los datos de perfil y contraseña.

    El email ya fue verificado por OTP, por lo que el usuario se crea directamente
    con is_verified=True y sin disparar el hook de envío de correo de verificación.
    """
    email = decode_verified_token(body.verified_token)
    if email is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token de verificación inválido o expirado")

    # Validar contraseña antes de tocar la BD
    try:
        await user_manager.validate_password(body.password, None)
    except InvalidPasswordException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña debe tener al menos 8 caracteres")

    # Comprobar que el email no está ya registrado
    try:
        await user_manager.get_by_email(email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")
    except UserNotExists:
        pass

    # Crear usuario directamente en BD (bypassa on_after_register → no envía email de verificación)
    hashed = user_manager.password_helper.hash(body.password)
    db_user = await user_manager.user_db.create({
        "email": email,
        "hashed_password": hashed,
        "is_active": True,
        "is_verified": True,
        "is_superuser": False,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "birth_date": body.birth_date,
        "gender": body.gender,
    })

    await send_welcome_email(db_user.email, db_user.first_name or "")

    return CompleteRegistrationResponse(
        id=str(db_user.id),
        email=db_user.email,
        first_name=db_user.first_name or "",
        last_name=db_user.last_name or "",
        is_verified=db_user.is_verified,
    )


@router.post(
    "/complete-google",
    response_model=CompleteGoogleRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_google_registration(
    body: CompleteGoogleRegistrationRequest,
    request: Request,
    user_manager=Depends(get_user_manager),
    db: AsyncSession = Depends(get_session),
    strategy=Depends(auth_backend.get_strategy),
) -> CompleteGoogleRegistrationResponse:
    """Crea la cuenta iniciada con Google: vincula OAuth y devuelve JWT de sesión."""
    data = decode_google_registration_token(body.google_token)
    if data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token de Google inválido o expirado")

    email = data["sub"]
    account_id = data["account_id"]
    google_access_token = data["google_access_token"]

    try:
        user = await user_manager.oauth_callback(
            oauth_name=google_oauth_client.name,
            access_token=google_access_token,
            account_id=account_id,
            account_email=email,
            expires_at=data.get("expires_at"),
            refresh_token=data.get("refresh_token"),
            request=request,
            associate_by_email=True,
            is_verified_by_default=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado") from exc

    # Guardar nombre obtenido de Google; birth_date y gender quedan null
    # (el usuario recibirá notificación para completarlos)
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.unique().scalar_one()
    db_user.first_name = data.get("first_name") or None
    db_user.last_name = data.get("last_name") or None
    await db.commit()

    await send_welcome_email(db_user.email, db_user.first_name or "")

    jwt_token = await strategy.write_token(db_user)
    return CompleteGoogleRegistrationResponse(access_token=jwt_token)
