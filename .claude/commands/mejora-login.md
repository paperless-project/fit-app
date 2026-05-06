# Mejora de la página de Login

Implementa tres mejoras en el sistema de autenticación del proyecto fit-app:
1. **Checkbox "Recordarme"** — sesión de 15 días en lugar de 8 horas
2. **Login con Google** — OAuth2 via Google, usando `fastapi-users` + `httpx-oauth`

---

## Alcance

### Backend (FastAPI)

#### 1. Checkbox "Recordarme" — dos backends JWT con lifetimes distintos

`fastapi-users` no admite lifetime variable por petición, así que se crean **dos `AuthenticationBackend`**:

- `auth_backend` — ya existe, 8 horas (`/auth/jwt/login`)
- `auth_backend_remember` — nuevo, 15 días (`/auth/jwt-remember/login`)

En `apps/api/src/fitapp/auth/users.py`:

```python
# Backend de "recordarme" — 15 días = 1_296_000 segundos
bearer_transport_remember = BearerTransport(tokenUrl="auth/jwt-remember/login")

def get_jwt_strategy_remember() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=1_296_000)

auth_backend_remember = AuthenticationBackend(
    name="jwt-remember",
    transport=bearer_transport_remember,
    get_strategy=get_jwt_strategy_remember,
)

# Registrar ambos backends en FastAPIUsers
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend, auth_backend_remember]
)
```

En `apps/api/src/fitapp/main.py`, montar el nuevo router de login:

```python
app.include_router(
    fastapi_users.get_auth_router(auth_backend_remember),
    prefix="/auth/jwt-remember",
    tags=["auth"],
)
```

No se necesita migración de BD para esto.

#### 2. Login con Google — OAuth2

**Prerrequisitos (el usuario debe tener credenciales de Google Cloud):**
- Ir a [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials
- Crear "OAuth 2.0 Client ID" de tipo "Web application"
- Añadir `http://localhost:8000/auth/google/callback` a "Authorized redirect URIs"
- Copiar `Client ID` y `Client Secret`

**Variables de entorno** — añadir a `docker-compose.yml` (sección `api > environment`) y a `.env` si existe:

```yaml
GOOGLE_OAUTH_CLIENT_ID: "${GOOGLE_OAUTH_CLIENT_ID}"
GOOGLE_OAUTH_CLIENT_SECRET: "${GOOGLE_OAUTH_CLIENT_SECRET}"
# URL base del frontend, para redirigir tras el callback
FRONTEND_URL: "http://localhost:5173"
```

**Dependencia** — añadir a `apps/api/pyproject.toml`:

```toml
"httpx-oauth>=0.15",
```

Tras modificar `pyproject.toml` es **obligatorio** hacer rebuild del venv:

```bash
docker compose down
docker volume rm fit-app_api_venv
docker compose up --build -d
```

**Config** — `apps/api/src/fitapp/config.py`:

```python
google_oauth_client_id: str = ""
google_oauth_client_secret: str = ""
frontend_url: str = "http://localhost:5173"
```

**Migración Alembic** — `fastapi-users` necesita la tabla `oauth_account`:

```bash
docker compose exec api alembic revision --autogenerate -m "add oauth_account table"
```

⚠️ Revisar el fichero generado: eliminar cualquier índice GiST falso positivo.

```bash
docker compose exec api alembic upgrade head
```

**Modelo User** — `apps/api/src/fitapp/models/user.py` debe incluir el mixin de OAuth:

```python
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID, SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import relationship

class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined"
    )
```

Si el modelo `User` ya existe con `SQLAlchemyBaseUserTableUUID`, solo añadir `OAuthAccount` y la relación.

**users.py** — conectar OAuth:

```python
from httpx_oauth.clients.google import GoogleOAuth2
from fitapp.config import settings

google_oauth_client = GoogleOAuth2(
    settings.google_oauth_client_id,
    settings.google_oauth_client_secret,
)

# Actualizar get_user_db para incluir oauth_accounts
async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
```

**main.py** — registrar el router OAuth:

```python
from fitapp.auth.users import google_oauth_client

app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,          # usa el backend estándar (8h)
        settings.jwt_secret,
        redirect_url=f"{settings.frontend_url}/auth/google/callback",
        is_verified_by_default=True,   # los usuarios de Google llegan verificados
    ),
    prefix="/auth/google",
    tags=["auth"],
)
```

### Tests (pytest)

Añadir en `apps/api/tests/test_auth.py` (o crear `test_auth_remember.py`):

- `test_login_with_remember_me`: login en `/auth/jwt-remember/login` devuelve token con lifetime ~15 días (verificar `exp` del JWT decodificado)
- `test_login_without_remember_me`: login en `/auth/jwt/login` devuelve token con lifetime ~8 horas
- No hace falta test de Google OAuth (requiere credenciales externas); documentar que es manual

Todos los tests existentes deben seguir pasando al 100%.

### Frontend (React + TypeScript)

#### 1. Checkbox "Recordarme" en `LoginPage.tsx`

Añadir estado:

```tsx
const [rememberMe, setRememberMe] = useState(false);
```

Checkbox en el formulario (entre contraseña y el botón):

```tsx
<label className="flex items-center gap-2 text-sm text-slate-600 select-none cursor-pointer">
  <input
    type="checkbox"
    checked={rememberMe}
    onChange={(e) => setRememberMe(e.target.checked)}
    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
  />
  Recordarme (15 días)
</label>
```

En `handleSubmit`, elegir el endpoint según el checkbox:

```tsx
const { access_token } = await loginApi(email, password, rememberMe);
```

Actualizar `loginApi` en `apps/web/src/lib/auth.ts`:

```ts
export async function loginApi(
  email: string,
  password: string,
  remember = false,
): Promise<LoginResponse> {
  const endpoint = remember ? '/auth/jwt-remember/login' : '/auth/jwt/login';
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, res.status);
  }
  return res.json() as Promise<LoginResponse>;
}
```

#### 2. Botón "Continuar con Google" en `LoginPage.tsx`

El flujo OAuth es una redirección del navegador (no fetch), así que el botón redirige al endpoint de autorización de Google via la API:

```tsx
function handleGoogleLogin() {
  // fastapi-users devuelve la URL de autorización de Google
  window.location.href = `${BASE_URL}/auth/google/authorize?scopes=openid%20email%20profile`;
}
```

Añadir antes del formulario (o después del botón "Entrar"), con divisor visual:

```tsx
{/* Divisor */}
<div className="relative my-4">
  <div className="absolute inset-0 flex items-center">
    <div className="w-full border-t border-slate-200" />
  </div>
  <div className="relative flex justify-center text-xs text-slate-400">
    <span className="bg-white px-2">o continúa con</span>
  </div>
</div>

{/* Botón Google */}
<button
  type="button"
  onClick={handleGoogleLogin}
  className="flex w-full items-center justify-center gap-3 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
>
  <svg className="h-4 w-4" viewBox="0 0 24 24">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
  Continuar con Google
</button>
```

#### 3. Página de callback OAuth — `apps/web/src/pages/OAuthCallbackPage.tsx`

Crear esta página para capturar el token que devuelve fastapi-users tras el redirect de Google:

```tsx
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getMeApi } from '@/lib/auth';
import { useAuthStore } from '@/store/authStore';

export default function OAuthCallbackPage() {
  const [params] = useSearchParams();
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    const token = params.get('access_token');
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }
    getMeApi(token).then((user) => {
      setAuth(token, user);
      navigate('/activities', { replace: true });
    }).catch(() => navigate('/login', { replace: true }));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <p className="text-sm text-slate-500">Autenticando con Google…</p>
    </div>
  );
}
```

Registrar la ruta en `apps/web/src/App.tsx`:

```tsx
import OAuthCallbackPage from '@/pages/OAuthCallbackPage';
// ...
<Route path="/auth/google/callback" element={<OAuthCallbackPage />} />
```

Esta ruta **no** debe estar dentro de `<PrivateRoute>`.

---

## Orden de implementación

1. **"Recordarme"** (sin dependencias externas):
   a. `auth/users.py`: añadir `auth_backend_remember`
   b. `main.py`: montar `/auth/jwt-remember`
   c. `lib/auth.ts`: actualizar `loginApi` con parámetro `remember`
   d. `LoginPage.tsx`: añadir checkbox
   e. Tests: `test_login_with_remember_me` y `test_login_without_remember_me`
   f. `docker compose exec api pytest` — todos verdes

2. **Login con Google** (requiere credenciales, puede dejarse para después):
   a. Obtener `GOOGLE_OAUTH_CLIENT_ID` y `GOOGLE_OAUTH_CLIENT_SECRET`
   b. Añadir `httpx-oauth` a `pyproject.toml` + rebuild venv
   c. Actualizar `config.py` con las nuevas variables
   d. Actualizar `models/user.py`: añadir `OAuthAccount` y relación
   e. Generar y revisar migración Alembic, aplicar
   f. Actualizar `auth/users.py`: `google_oauth_client` + `get_user_db` con OAuthAccount
   g. `main.py`: montar `/auth/google`
   h. Frontend: botón Google en `LoginPage`, crear `OAuthCallbackPage`, registrar ruta
   i. Probar manualmente el flujo completo en el navegador

---

## Convenciones del proyecto

- Seguir el stack existente: `fastapi-users`, TanStack Query, Zustand, Tailwind
- No hay cambios de esquema para "Recordarme" → no se necesita migración
- Para Google OAuth sí hay migración → revisarla antes de aplicar (índices GiST falsos positivos)
- Una fase no se da por completada hasta que todos los tests pasen al 100%
- Si las credenciales de Google no están disponibles, implementar y documentar la parte del código pero no ejecutar el test de integración OAuth
