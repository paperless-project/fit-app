# Frontend (React + Vite)

## Estructura src/
```
App.tsx                  Rutas: /login /register /verify (públicas) + /activities /activities/:id (privadas)
main.tsx                 QueryClientProvider + BrowserRouter
store/authStore.ts       Zustand: token(localStorage), user, isInitialized
lib/api.ts               fetch wrapper genérico; manejo global 401 → logout + redirect /login
lib/auth.ts              loginApi, registerApi, getMeApi, logoutApi, verifyEmailApi
lib/activities.ts        getActivitiesApi, getActivityDetailApi, uploadActivityApi
types/user.ts            UserRead, LoginResponse
types/activity.ts        Activity, ActivityDetail, RecordPoint, LapPoint
components/
  PrivateRoute.tsx       Spinner si !isInitialized; redirect /login si !token
  Layout.tsx             Navbar: link home, email usuario, botón logout
  ActivityMap.tsx        react-leaflet: polyline GPS, marcadores inicio/fin, CircleMarker hover
  ActivityCharts.tsx     react-chartjs-2: altitud(area), velocidad, FC, cadencia, potencia;
                         crosshair plugin sincronizado; tooltip muestra km
pages/
  LoginPage.tsx
  RegisterPage.tsx
  VerifyPage.tsx         Lee ?token= → POST /auth/verify → éxito/error
  ActivitiesPage.tsx     Tabla actividades + modal upload drag-and-drop; filas → navigate /activities/:id
  ActivityDetailPage.tsx Header stats, ActivityMap, ActivityCharts, LapsTable; hoverIdx shared state
```

## Sincronización mapa ↔ gráficas
- `hoverIdx: number | null` en `ActivityDetailPage` (useState)
- `ActivityCharts.onHover(idx)` → actualiza hoverIdx
- `ActivityMap` recibe hoverIdx → mueve `CircleMarker` a `records[hoverIdx]`
- Crosshair en cada chart via plugin custom con `useRef` (evita recrear plugin en cada render)

## Leaflet en Vite
- Iconos rotos por Vite bundling → fix manual con `new URL('leaflet/dist/images/...', import.meta.url).href`
- `FitBounds` component auxiliar dentro del `MapContainer` que llama `map.fitBounds()` via `useMap()`
- `HoverMarker` component usa `useEffect` para crear/mover/destruir `L.circleMarker` imperativo

## TanStack Query
- Clave `['activities']` → lista; `['activity', id]` → detalle
- Upload invalida `['activities']` via `queryClient.invalidateQueries`

## Convenciones
- `VITE_API_URL` → `http://localhost:8000` por defecto
- JWT en `localStorage` como `access_token`
- Alias `@/` → `src/`
- `pnpm run build` debe compilar sin errores (TypeScript strict) antes de dar por buena cualquier cambio

## Dependencias clave
```
leaflet + react-leaflet + @types/leaflet
chart.js + react-chartjs-2
@tanstack/react-query
zustand
react-router-dom
tailwindcss
```
