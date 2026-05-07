# Frontend (React + Vite)

## Rutas (App.tsx)
```
Públicas:  /login  /register  /verify  /auth/google/callback
Privadas:  /activities  /activities/:id  /stats  /calendar  /account
```

## Estructura src/
```
main.tsx             QueryClientProvider + BrowserRouter
store/authStore.ts   Zustand: token(localStorage), user(UserRead), isInitialized
                     setUser() actualiza perfil sin re-login
lib/api.ts           fetch wrapper; 401 global → removeItem + redirect /login
lib/auth.ts          loginApi, registerApi, getMeApi, logoutApi, verifyEmailApi
lib/activities.ts    getActivitiesApi(filters+pagination), getActivityDetailApi, uploadActivityApi,
                     patchActivityApi, deleteActivityApi, downloadGpxApi, downloadCsvApi
lib/stats.ts         getStatsSummaryApi, getStatsCalendarApi(year), getStatsTimelineApi(bucket),
                     getCalendarDetailApi(year), recalculateNPApi
lib/account.ts       changePasswordApi, deleteAccountApi, updateTrainingProfileApi
lib/strava.ts        getStravaStatus, connectStrava (fetch→{authorization_url}→redirect),
                     disconnectStrava, startStravaImport(after?, before?)
types/user.ts        UserRead (incl. first_name, last_name, birth_date, gender, ftp, weight_kg)
types/activity.ts    Activity, ActivityDetail, ActivityFilters (incl. page/size), RecordPoint, LapPoint
types/stats.ts       StatsSummary, CalendarDay, TimelineEntry, CalendarDetailResponse, WeekSummary

components/
  PrivateRoute.tsx   Spinner si !isInitialized; redirect /login si !token
  Layout.tsx         Navbar: logo, links, campanilla "Faltan datos" (birth_date||gender null),
                     email usuario → /account, logout
  Pagination.tsx     prev/next + numeración; usado en ActivitiesPage
  ActivityMap.tsx    react-leaflet: polyline, marcadores inicio/fin, CircleMarker hover
  ActivityCharts.tsx react-chartjs-2: altitud, velocidad, FC, cadencia, potencia;
                     crosshair plugin sincronizado; oculta gráficas sin datos

pages/
  LoginPage.tsx          form email+password + botón Google OAuth (flow=login)
  RegisterPage.tsx       3 pasos OTP + Google OAuth (flow=register); auto-completa con google_token
  VerifyPage.tsx         lee ?token= → POST /auth/verify
  OAuthCallbackPage.tsx  captura ?access_token= → authStore → redirect /activities
  ActivitiesPage.tsx     FilterBar, tabla, Pagination, modal upload, botón CSV
  ActivityDetailPage.tsx stats, ActivityMap, ActivityCharts, LapsTable, EditModal, botón GPX, botón borrar
  StatsPage.tsx          SummaryCards, CalendarHeatmap (GitHub-style), TimelineChart barras
  CalendarPage.tsx       resumen año, cuadrícula semanas (dist/tiempo/cal/TSS/IF por semana)
  AccountPage.tsx        ChangePasswordSection, TrainingProfileSection, StravaSection, DangerZone
```

## TanStack Query — claves de caché
```
['activities', filters]           lista con filtros+paginación
['activity', id]                  detalle
['stats', 'summary']
['stats', 'calendar', year]
['stats', 'calendar-detail', year]
['stats', 'timeline', bucket]
['strava-status']                 polling cada 10s mientras importing=true
```

## Sección Strava (AccountPage)
- `useQuery(['strava-status'])` con `refetchInterval: importing ? 10_000 : false`
- Botón "Conectar con Strava" → `connectStrava()`: fetch Bearer → `{authorization_url}` → `window.location.href`
- Botón "Importar actividades" + rango fechas (after/before como epoch)
- Spinner persistente con `importing` local; se apaga cuando `last_import_at` cambia
- Gestiona `?strava_connected=1` y `?strava_error=...` al montar la página

## Gotchas Leaflet en Vite
- Iconos rotos → fix con `new URL('leaflet/dist/images/...', import.meta.url).href`
- `FitBounds` dentro de `MapContainer` → `map.fitBounds()` via `useMap()`
- `HoverMarker` → `L.circleMarker` imperativo via `useEffect`

## Convenciones
- `VITE_API_URL` → `http://localhost:8000` por defecto
- JWT en `localStorage` como `access_token`
- Alias `@/` → `src/`
- `pnpm tsc --noEmit` debe pasar sin errores antes de dar cambio por bueno
