# Frontend (React + Vite)

## Estructura src/
```
App.tsx              Rutas: /login /register /verify (públicas) + /activities /activities/:id /stats (privadas)
main.tsx             QueryClientProvider + BrowserRouter
store/authStore.ts   Zustand: token(localStorage), user, isInitialized
lib/api.ts           fetch wrapper + downloadFile() (blob→anchor); 401 global → logout + redirect /login
lib/auth.ts          loginApi, registerApi, getMeApi, logoutApi, verifyEmailApi
lib/activities.ts    getActivitiesApi(filters), getActivityDetailApi, uploadActivityApi,
                     patchActivityApi, downloadGpxApi, downloadCsvApi(filters)
lib/stats.ts         getStatsSummaryApi, getStatsCalendarApi(year), getStatsTimelineApi(bucket)
types/user.ts        UserRead, LoginResponse
types/activity.ts    Activity (incl. notes), ActivityDetail, ActivityFilters, RecordPoint, LapPoint
types/stats.ts       StatsSummary, CalendarDay, CalendarResponse, TimelineEntry

components/
  PrivateRoute.tsx   Spinner si !isInitialized; redirect /login si !token
  Layout.tsx         Navbar: logo, links (Actividades / Estadísticas), email usuario, logout
  ActivityMap.tsx    react-leaflet: polyline GPS, marcadores inicio/fin, CircleMarker hover
  ActivityCharts.tsx react-chartjs-2: altitud(area), velocidad, FC, cadencia, potencia;
                     crosshair plugin sincronizado; tooltip muestra km

pages/
  LoginPage.tsx
  RegisterPage.tsx
  VerifyPage.tsx           Lee ?token= → POST /auth/verify → éxito/error
  ActivitiesPage.tsx       FilterBar (q/sport/dates), tabla actividades, botón "Exportar CSV",
                           modal upload drag-and-drop; filas → navigate /activities/:id
  ActivityDetailPage.tsx   Header stats, ActivityMap, ActivityCharts, LapsTable;
                           EditModal (name/sport/notes), botón "Descargar GPX"; hoverIdx shared
  StatsPage.tsx            SummaryCards (4 tarjetas), CalendarHeatmap (grid GitHub-style + selector año),
                           TimelineChart (barras Chart.js distancia/tiempo mensual)
```

## Sincronización mapa ↔ gráficas
- `hoverIdx: number | null` en `ActivityDetailPage` (useState)
- `ActivityCharts.onHover(idx)` → actualiza hoverIdx
- `ActivityMap` recibe hoverIdx → mueve `CircleMarker` a `records[hoverIdx]`
- Crosshair en cada chart via plugin custom con `useRef` (evita recrear en cada render)

## Leaflet en Vite
- Iconos rotos por Vite bundling → fix manual con `new URL('leaflet/dist/images/...', import.meta.url).href`
- `FitBounds` component dentro del `MapContainer` → `map.fitBounds()` via `useMap()`
- `HoverMarker` usa `useEffect` para crear/mover/destruir `L.circleMarker` imperativo

## TanStack Query — claves de caché
- `['activities', filters]` → lista con filtros aplicados
- `['activity', id]` → detalle
- `['stats', 'summary']`, `['stats', 'calendar', year]`, `['stats', 'timeline', bucket]`
- Upload/PATCH invalidan `['activities']` y `['activity', id]` según corresponda

## CalendarHeatmap
- Grid puro React/Tailwind: 7 filas (días) × ~53 columnas (semanas)
- Colores Tailwind: vacío→gray-100, 1act→green-200, 2→green-400, 3→green-600, 4+→green-800
- Selector de año via `<select>` controlado, rango: primer año de datos hasta año actual

## Descargas (GPX / CSV)
- `downloadFile(url, filename, token)` en `lib/api.ts`: fetch con auth → blob → `URL.createObjectURL` → anchor click
- No abre nueva pestaña; funciona con archivos grandes

## Convenciones
- `VITE_API_URL` → `http://localhost:8000` por defecto
- JWT en `localStorage` como `access_token`
- Alias `@/` → `src/`
- `pnpm run build` debe compilar sin errores TypeScript antes de dar por buena cualquier cambio

## Dependencias clave
```
leaflet + react-leaflet + @types/leaflet
chart.js + react-chartjs-2
@tanstack/react-query
zustand
react-router-dom
tailwindcss
```
