# Frontend (React + Vite)

## Estado actual — Fase 1 completa ✅

```
src/
├── App.tsx                  Rutas: /login, /register, /verify (públicas) + /activities (privada)
├── main.tsx                 QueryClientProvider + BrowserRouter
├── store/authStore.ts       Zustand: token (localStorage), user, isInitialized
├── lib/auth.ts              loginApi, registerApi, getMeApi, logoutApi, verifyEmailApi
├── lib/api.ts               fetch wrapper; manejo global 401 → logout + redirect /login
├── types/user.ts            UserRead, LoginResponse
├── components/
│   ├── PrivateRoute.tsx     Spinner si !isInitialized; redirect /login si !token
│   └── Layout.tsx           Navbar: "fit-app" link, email usuario, botón logout
└── pages/
    ├── LoginPage.tsx        Formulario email/password → /activities
    ├── RegisterPage.tsx     Formulario email/password/confirmar → /login
    ├── VerifyPage.tsx       Lee ?token= → POST /auth/verify → muestra éxito/error
    └── ActivitiesPage.tsx   Placeholder "Próximamente" (Fase 3)
```

## Flujo de autenticación
1. Mount de App: si hay token en localStorage → GET /users/me → `setUser` o `logout`
2. `PrivateRoute`: muestra spinner hasta `isInitialized`, luego redirige si !token
3. Login → `setAuth(token, user)` → guarda en localStorage → navega a /activities
4. Logout → `logout()` → limpia localStorage → navega a /login
5. Cualquier 401 de la API → `api.ts` limpia token y redirige a /login

## Flujo verificación email
1. Register → backend envía email con enlace `http://localhost:5173/verify?token=TOKEN`
2. Usuario pincha enlace → `VerifyPage` extrae token de URL → POST /auth/verify
3. Éxito: mensaje confirmación + botón a /login
4. Error/caducado: mensaje de error + botón a /login

## Pendiente implementar (Fase 3+)
- `ActivitiesPage`: tabla de actividades, filtros, paginación
- `ActivityDetailPage`: mapa Leaflet + gráficas Chart.js sincronizadas
- Stats dashboard: heatmap calendario, evolución mensual
- Upload de fichero .fit

## Convenciones
- `VITE_API_URL` en `.env` → `http://localhost:8000`
- JWT en `localStorage` como `access_token`
- Alias `@/` → `src/`
- `pnpm run build` debe compilar sin errores antes de dar por buena cualquier cambio frontend
