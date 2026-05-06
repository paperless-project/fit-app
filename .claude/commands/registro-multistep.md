# Registro multi-paso con OTP y Google

Implementa dos flujos de registro alternativos:

## Flujo por email (3 pasos)
- **Paso 1**: El usuario introduce su email → se envía un OTP de 6 dígitos por email
- **Paso 2**: El usuario introduce el OTP → si coincide, se valida y se genera un `verified_token`
- **Paso 3**: El usuario rellena Nombre, Apellidos, Fecha de nacimiento, Género y Contraseña → se crea la cuenta

## Flujo por Google (1 paso)
- El usuario hace clic en "Registrarse con Google" en la página de registro
- Si Google devuelve un perfil sin cuenta en fit-app, el backend genera un `google_registration_token` (JWT corto con email + nombre + datos de OAuth)
- El frontend redirige a `/register?google_token=...` y salta directamente al **Paso 3** (perfil), con Nombre y Apellidos pre-rellenados desde Google y **sin campo de contraseña** (el usuario sólo podrá entrar con Google)
- Se crea la cuenta y se vincula automáticamente la cuenta OAuth

Los campos de perfil nuevos son: `first_name`, `last_name`, `birth_date` (date), `gender` (enum).

---

## Reglas antes de empezar

- **No marcar la fase como completada hasta que todos los tests pasen al 100%.**
- Siempre revisar el fichero de migración Alembic generado antes de aplicarlo (eliminar falsos positivos de índices GiST).
- No introducir abstracciones innecesarias ni código especulativo.

---

## Pasos de implementación

### 1. Modelo OTP (`apps/api/src/fitapp/models/email_otp.py`)

Crear el modelo SQLAlchemy para almacenar los OTP pendientes:

```python
import uuid
import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from fitapp.database import Base

class EmailOTP(Base):
    __tablename__ = "email_otp"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Exportar desde `models/__init__.py`.

---

### 2. Columnas nuevas en el modelo User (`apps/api/src/fitapp/models/user.py`)

Añadir a la clase `User` (que hereda de `SQLAlchemyBaseUserTableUUID`):

```python
import enum
import datetime
from sqlalchemy import String, Date, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

class Gender(str, enum.Enum):
    hombre = "hombre"
    mujer = "mujer"
    no_binario = "no_binario"
    prefiero_no_decirlo = "prefiero_no_decirlo"
    otro = "otro"

# Dentro de class User:
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, name="gender_enum"), nullable=True)
```

El enum `Gender` debe definirse en `models/user.py` (o en un fichero `models/enums.py` exportado desde `models/__init__.py`).

---

### 3. Schemas Pydantic actualizados (`apps/api/src/fitapp/schemas/user.py`)

```python
import datetime
import uuid
from fastapi_users import schemas
from fitapp.models.user import Gender  # importar el enum

class UserRead(schemas.BaseUser[uuid.UUID]):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: datetime.date | None = None
    gender: Gender | None = None

    model_config = {"from_attributes": True}

class UserCreate(schemas.BaseUserCreate):
    # Mantener solo password aquí — el registro multi-paso
    # crea el usuario en /auth/register/complete
    pass

class UserUpdate(schemas.BaseUserUpdate):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: datetime.date | None = None
    gender: Gender | None = None
```

Schemas para el flujo OTP (pueden ir en `schemas/register.py` nuevo):

```python
from pydantic import BaseModel, EmailStr
import datetime
from fitapp.models.user import Gender

class SendOTPRequest(BaseModel):
    email: EmailStr

class SendOTPResponse(BaseModel):
    message: str  # "OTP enviado"

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str

class VerifyOTPResponse(BaseModel):
    verified_token: str  # JWT corto (30 min) que prueba que el email fue verificado

class CompleteRegistrationRequest(BaseModel):
    verified_token: str
    first_name: str
    last_name: str
    birth_date: datetime.date
    gender: Gender
    password: str

class CompleteRegistrationResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    is_verified: bool

# Flujo Google
class CompleteGoogleRegistrationRequest(BaseModel):
    google_token: str   # JWT con datos OAuth de Google
    first_name: str
    last_name: str
    birth_date: datetime.date
    gender: Gender
    # Sin contraseña — el usuario sólo puede entrar con Google

class CompleteGoogleRegistrationResponse(BaseModel):
    access_token: str   # JWT de sesión fit-app (igual que el login normal)
    token_type: str = "bearer"
```

---

### 4. Servicio OTP (`apps/api/src/fitapp/services/otp.py`)

```python
import random
import datetime
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fitapp.models.email_otp import EmailOTP
from fitapp.config import settings

OTP_EXPIRY_MINUTES = 10
OTP_VERIFIED_TOKEN_MINUTES = 30

def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"

async def create_otp(db: AsyncSession, email: str) -> str:
    """Genera y guarda un OTP. Invalida OTPs anteriores del mismo email."""
    # Eliminar OTPs anteriores del mismo email
    await db.execute(delete(EmailOTP).where(EmailOTP.email == email))
    
    code = _generate_code()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    otp = EmailOTP(email=email, code=code, expires_at=expires_at)
    db.add(otp)
    await db.commit()
    return code

async def verify_otp(db: AsyncSession, email: str, code: str) -> bool:
    """Verifica el OTP. Devuelve True si es válido y lo marca como usado."""
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await db.execute(
        select(EmailOTP).where(
            EmailOTP.email == email,
            EmailOTP.code == code,
            EmailOTP.used == False,
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
    """Genera un JWT de corta duración que certifica que el email fue verificado por OTP."""
    payload = {
        "sub": email,
        "type": "otp_verified",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_VERIFIED_TOKEN_MINUTES),
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


GOOGLE_REG_TOKEN_MINUTES = 30

def create_google_registration_token(
    email: str,
    first_name: str | None,
    last_name: str | None,
    account_id: str,
    google_access_token: str,
    expires_at: int | None,
    refresh_token: str | None,
) -> str:
    """JWT de 30 min que certifica que el email fue verificado por Google y contiene los datos OAuth."""
    payload = {
        "sub": email,
        "type": "google_registration",
        "first_name": first_name or "",
        "last_name": last_name or "",
        "account_id": account_id,
        "google_access_token": google_access_token,
        "expires_at": expires_at,
        "refresh_token": refresh_token,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=GOOGLE_REG_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_google_registration_token(token: str) -> dict | None:
    """Decodifica el google_registration_token. Devuelve el payload o None si es inválido/expirado."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "google_registration":
            return None
        return payload
    except jwt.PyJWTError:
        return None
```

---

### 5. Email OTP (`apps/api/src/fitapp/services/email.py`)

Añadir la función `send_otp_email` al fichero existente:

```python
async def send_otp_email(email: str, code: str) -> None:
    if not settings.smtp_host:
        return
    body_html = f"""
    <p>Tu código de verificación para <strong>fit-app</strong> es:</p>
    <h2 style="letter-spacing: 8px; font-size: 36px;">{code}</h2>
    <p>Este código caduca en <strong>10 minutos</strong>.</p>
    <p>Si no has solicitado este código, ignora este mensaje.</p>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Código de verificación — fit-app"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.attach(MIMEText(body_html, "html"))

    def _send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
            if settings.smtp_starttls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.smtp_from, [email], msg.as_string())

    await asyncio.to_thread(_send)
```

---

### 6. Router de registro multi-paso (`apps/api/src/fitapp/routers/register.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.exceptions import UserAlreadyExists

from fitapp.database import get_async_session
from fitapp.schemas.register import (
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    CompleteRegistrationRequest, CompleteRegistrationResponse,
)
from fitapp.services.otp import create_otp, verify_otp, create_verified_token, decode_verified_token
from fitapp.services.email import send_otp_email
from fitapp.auth.users import get_user_manager
from fitapp.models.user import User

router = APIRouter(prefix="/auth/register", tags=["register"])


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(
    body: SendOTPRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Paso 1: enviar OTP al email proporcionado."""
    code = await create_otp(db, body.email)
    await send_otp_email(body.email, code)
    return SendOTPResponse(message="OTP enviado")


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp_endpoint(
    body: VerifyOTPRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Paso 2: verificar OTP. Devuelve verified_token si es correcto."""
    valid = await verify_otp(db, body.email, body.code)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código incorrecto o expirado")
    token = create_verified_token(body.email)
    return VerifyOTPResponse(verified_token=token)


@router.post("/complete", response_model=CompleteRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def complete_registration(
    body: CompleteRegistrationRequest,
    user_manager=Depends(get_user_manager),
    db: AsyncSession = Depends(get_async_session),
):
    """Paso 3: completar registro con datos de perfil y contraseña."""
    email = decode_verified_token(body.verified_token)
    if email is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token de verificación inválido o expirado")

    from fitapp.schemas.user import UserCreate
    try:
        user = await user_manager.create(
            UserCreate(email=email, password=body.password),
            safe=True,
        )
    except UserAlreadyExists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")

    # Añadir campos de perfil directamente (fuera del flujo fastapi-users)
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()
    db_user.first_name = body.first_name
    db_user.last_name = body.last_name
    db_user.birth_date = body.birth_date
    db_user.gender = body.gender
    db_user.is_verified = True  # email ya fue verificado por OTP
    await db.commit()
    await db.refresh(db_user)

    return CompleteRegistrationResponse(
        id=str(db_user.id),
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        is_verified=db_user.is_verified,
    )


@router.post("/complete-google", response_model=CompleteGoogleRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def complete_google_registration(
    body: CompleteGoogleRegistrationRequest,
    request: Request,
    user_manager=Depends(get_user_manager),
    db: AsyncSession = Depends(get_async_session),
    strategy=Depends(auth_backend.get_strategy),
):
    """Completa el registro iniciado con Google: crea usuario + vincula cuenta OAuth + devuelve JWT."""
    from fitapp.services.otp import decode_google_registration_token
    from fitapp.auth.users import google_oauth_client

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

    # Guardar datos de perfil
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()
    db_user.first_name = body.first_name
    db_user.last_name = body.last_name
    db_user.birth_date = body.birth_date
    db_user.gender = body.gender
    await db.commit()

    jwt_token = await strategy.write_token(db_user)
    return CompleteGoogleRegistrationResponse(access_token=jwt_token)
```

---

### 7. Modificar `google_callback.py` para el flujo de registro

Cuando el usuario de Google no tiene cuenta en fit-app, en lugar de redirigir con `google_error`, hay que:
1. Obtener el nombre y apellido del perfil Google via `get_id_email` ampliado (ver más abajo)
2. Crear un `google_registration_token` con todos los datos OAuth
3. Redirigir a `/register?google_token=...`

En `google_callback.py`, sustituir el bloque `if not user_exists:` actual:

```python
# ANTES (eliminar):
if not user_exists:
    qs = urllib.parse.urlencode({
        "google_error": "No existe una cuenta de fit-app para este perfil de Google.",
    })
    return RedirectResponse(f"{settings.frontend_url}/register?{qs}", status_code=302)

# DESPUÉS (añadir):
if not user_exists:
    from fitapp.services.otp import create_google_registration_token
    # Obtener nombre/apellido del perfil Google
    profile = await google_oauth_client.get_profile(token["access_token"])
    first_name = profile.get("given_name", "")
    last_name = profile.get("family_name", "")

    reg_token = create_google_registration_token(
        email=account_email,
        first_name=first_name,
        last_name=last_name,
        account_id=account_id,
        google_access_token=token["access_token"],
        expires_at=token.get("expires_at"),
        refresh_token=token.get("refresh_token"),
    )
    qs = urllib.parse.urlencode({"google_token": reg_token})
    return RedirectResponse(f"{settings.frontend_url}/register?{qs}", status_code=302)
```

**Importante**: `_GoogleOAuth2` ya usa `/oauth2/v2/userinfo` para `get_id_email`. Ese endpoint devuelve `given_name` y `family_name`. Añadir el método `get_profile` a la subclase `_GoogleOAuth2` en `auth/users.py`:

```python
async def get_profile(self, token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()
```

---

### 8. Registrar el router en `main.py`

En `apps/api/src/fitapp/main.py`:

- **Eliminar** (o comentar) la línea que añade `fastapi_users.get_register_router(...)` — ya no usamos el endpoint genérico `/auth/register`.
- **Añadir** el nuevo router antes de los demás routers de fastapi-users:

```python
from fitapp.routers.register import router as register_router
app.include_router(register_router)
```

El orden importa: incluirlo **antes** del router de fastapi-users para evitar colisiones de rutas.

---

### 8. Migración Alembic

```bash
docker compose exec api alembic revision --autogenerate -m "add email_otp table and user profile fields"
```

Revisar el fichero generado en `alembic/versions/`:
- Debe crear tabla `email_otp` con columnas `id`, `email`, `code`, `expires_at`, `used`
- Debe añadir columnas `first_name`, `last_name`, `birth_date`, `gender` a tabla `users`
- Debe crear el tipo enum `gender_enum` en PostgreSQL
- **Eliminar cualquier operación sobre índices GiST o tablas PostGIS** que aparezcan como falsos positivos

Aplicar:
```bash
docker compose exec api alembic upgrade head
```

---

### 9. Tests (`apps/api/tests/test_register_multistep.py`)

Crear tests para los 3 endpoints nuevos. Cubrir:

**`POST /auth/register/send-otp`**
- 200 + `message="OTP enviado"` con email válido
- El OTP se guarda en BD con `used=False` y `expires_at` futuro
- Un segundo envío al mismo email invalida el primero (el anterior desaparece)

**`POST /auth/register/verify-otp`**
- 200 + `verified_token` (string no vacío) con código correcto
- 400 con código incorrecto
- 400 con código expirado (manipular `expires_at` en BD)
- 400 con código ya usado

**`POST /auth/register/complete`**
- 201 + datos de usuario con `verified_token` válido + datos correctos
- 400 con `verified_token` inválido
- 400 con `verified_token` expirado
- 409 si el email ya está registrado
- El usuario creado tiene `is_verified=True`
- Los campos de perfil se guardan correctamente

**Flujo completo de punta a punta (email):**
- send-otp → extraer código de BD → verify-otp → complete → login funciona

**`POST /auth/register/complete-google`**
- 201 + `access_token` con `google_token` válido + datos correctos
- 400 con `google_token` inválido
- 400 con `google_token` expirado
- 409 si el email ya está registrado
- El usuario creado tiene `is_verified=True` y los campos de perfil guardados
- El `access_token` devuelto permite llamar a `GET /users/me` con éxito

Usar mocks para el envío de email y para OAuth:
```python
@patch("fitapp.routers.register.send_otp_email", new_callable=AsyncMock)
# Para complete-google: parchear user_manager.oauth_callback si se necesita aislar la BD OAuth
```

Para los tests de `complete-google`, crear el `google_token` directamente con `create_google_registration_token` (importado desde el servicio) con datos ficticios — no hace falta pasar por Google real.

---

### 10. Frontend — Tipos (`apps/web/src/types/user.ts`)

Actualizar `UserRead`:
```typescript
export interface UserRead {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;  // ISO date "YYYY-MM-DD"
  gender: 'hombre' | 'mujer' | 'no_binario' | 'prefiero_no_decirlo' | 'otro' | null;
}
```

---

### 11. Frontend — API (`apps/web/src/lib/auth.ts`)

Añadir las tres funciones nuevas (mantener las existentes):

```typescript
const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function sendOTPApi(email: string): Promise<void> {
  const res = await fetch(`${API}/auth/register/send-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Error al enviar el código');
  }
}

export async function verifyOTPApi(email: string, code: string): Promise<string> {
  const res = await fetch(`${API}/auth/register/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Código incorrecto o expirado');
  }
  const data = await res.json();
  return data.verified_token as string;
}

export async function completeRegistrationApi(payload: {
  verified_token: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  password: string;
}): Promise<{ email: string }> {
  const res = await fetch(`${API}/auth/register/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Error al crear la cuenta');
  }
  return res.json();
}

export async function completeGoogleRegistrationApi(payload: {
  google_token: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
}): Promise<{ access_token: string; token_type: string }> {
  const res = await fetch(`${API}/auth/register/complete-google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? 'Error al crear la cuenta con Google');
  }
  return res.json();
}
```

---

### 12. Frontend — RegisterPage multi-paso (`apps/web/src/pages/RegisterPage.tsx`)

Reemplazar completamente `RegisterPage.tsx` con un componente multi-step. El estado del componente controla el paso actual:

```typescript
type Step = 'email' | 'otp' | 'profile';
```

**Paso `email`:**
- Input de email
- Botón "Enviar código" → llama `sendOTPApi(email)` → avanza a `otp`
- Mostrar spinner mientras carga
- Mostrar error si falla

**Paso `otp`:**
- Texto informativo: "Hemos enviado un código de 6 dígitos a {email}"
- Input para el código OTP (maxLength=6, type="text", pattern="[0-9]*")
- Botón "Verificar código" → llama `verifyOTPApi(email, code)` → guarda `verifiedToken` → avanza a `profile`
- Enlace "Reenviar código" → llama `sendOTPApi(email)` de nuevo
- Mostrar error si el código es incorrecto

**Paso `profile`** (flujo email):
- Input "Nombre" (first_name)
- Input "Apellidos" (last_name)
- Input date "Fecha de nacimiento" (birth_date, type="date")
- Select "Género":
  - `hombre` → "Hombre"
  - `mujer` → "Mujer"
  - `no_binario` → "No binario"
  - `prefiero_no_decirlo` → "Prefiero no decirlo"
  - `otro` → "Otro"
- Input "Contraseña" (password, type="password")
- Input "Confirmar contraseña" (confirm, type="password")
- Validación: password === confirm, mínimo 8 caracteres
- Botón "Crear cuenta" → llama `completeRegistrationApi({verified_token, first_name, last_name, birth_date, gender, password})`
- En éxito: `navigate('/login', { state: { registered: true } })`
- Mostrar error si falla

**Paso `profile`** (flujo Google — activado cuando `?google_token=` está en la URL):
- El componente detecta `?google_token=` al montar → extrae `googleToken` del query param y va directamente al paso `profile` (saltándose email y OTP)
- Los campos Nombre y Apellidos se pre-rellenan con los valores del token decodificado (pasados via URL o extraídos del JWT — preferiblemente con un campo adicional en el redirect del backend, como `?google_token=...&first_name=...&last_name=...` para evitar decodificar JWT en el cliente)
- Los campos Fecha de nacimiento y Género están vacíos (el usuario debe rellenarlos)
- **No hay campo de contraseña** en el flujo Google
- Botón "Crear cuenta con Google" → llama `completeGoogleRegistrationApi({google_token, first_name, last_name, birth_date, gender})`
- En éxito: llama `getMeApi(access_token)` → `setAuth(token, user)` → `navigate('/activities')` (queda logado directamente)
- Mostrar error si falla

**Botón "Registrarse con Google"** en el paso `email`:
- Aparece junto al formulario de email, separado con un divisor "o"
- Al hacer clic llama a `GET /auth/google/authorize?scopes=openid&scopes=email&scopes=profile` con `credentials: 'include'` (idéntico al botón en LoginPage)
- Redirige al navegador a la URL de Google recibida

Usar Tailwind para estilos, consistente con el resto de páginas del proyecto (ver LoginPage.tsx como referencia de clases).

El componente debe mostrar el paso actual visualmente (por ejemplo, "Paso 1 de 3 — Verificación de email"). En el flujo Google se puede mostrar directamente "Completa tu perfil — Registro con Google".

Eliminar el manejo de `?google_error=` del RegisterPage original, ya que ese escenario ahora deriva al flujo Google.

---

### 13. Verificar que todo funciona

```bash
# Ejecutar todos los tests
docker compose exec api pytest

# Solo los nuevos tests
docker compose exec api pytest tests/test_register_multistep.py -v

# Arrancar frontend y probar en navegador (http://localhost:5173/register)
```

**Flujo email manual:**
1. Abrir `/register` → aparece "Paso 1 de 3 — Verificación de email"
2. Introducir email → clic "Enviar código" → aparece "Paso 2 de 3 — Verificar email"
3. Ir a Mailpit (http://localhost:8026) → abrir email → copiar código de 6 dígitos
4. Introducir código → clic "Verificar código" → aparece "Paso 3 de 3 — Completa tu perfil"
5. Rellenar Nombre, Apellidos, Fecha nacimiento, Género, Contraseña → clic "Crear cuenta"
6. Redirige a `/login` con mensaje de éxito
7. Hacer login con el email y contraseña → funciona y llega a `/activities`

**Flujo Google manual (requiere credenciales OAuth configuradas):**
1. Abrir `/register` → clic "Registrarse con Google" → redirige a Google
2. Autenticarse → si no tiene cuenta, redirige a `/register?google_token=...`
3. Aparece directamente "Completa tu perfil — Registro con Google" con Nombre/Apellidos pre-rellenados
4. Rellenar Fecha nacimiento y Género → clic "Crear cuenta con Google"
5. Redirige directamente a `/activities` (ya logado)

---

### 14. Actualizar documentación

Una vez todos los tests pasen, ejecutar `/sync-docs` para actualizar CLAUDE.md, README.md y doc/PLAN.md.
