# Frontend (React + Vite)

## Estado actual
- Arranca en `:5173` con hot-reload
- `HomePage` llama a `GET /health` y muestra el estado
- `src/lib/api.ts` — cliente fetch con JWT desde `localStorage`
- Sin login, sin rutas protegidas, sin ninguna pantalla funcional más allá del health check

## Estructura
```
src/
├── App.tsx              React Router con una ruta: / → HomePage
├── main.tsx             QueryClientProvider + BrowserRouter
├── index.css            @tailwind directives
├── lib/api.ts           fetch wrapper con Bearer token
├── pages/HomePage.tsx   health check
├── components/          (vacío)
├── hooks/               (vacío)
├── types/               (vacío — pendiente gen:api)
└── vite-env.d.ts        VITE_API_URL
```

## Dependencias instaladas
- `react`, `react-dom`, `react-router-dom`
- `@tanstack/react-query`
- `chart.js`, `react-chartjs-2`
- `leaflet`, `react-leaflet`
- `zustand`
- `tailwindcss`, `postcss`, `autoprefixer`
- `openapi-typescript` (gen:api)

## Pendiente implementar
1. Página de login + guard de rutas (redirige a `/login` si no hay token)
2. Listado de actividades con filtros y paginación
3. Detalle: mapa Leaflet de la ruta, gráficas sincronizadas (altitud, velocidad, FC)
4. Tabla de laps
5. Dashboard estadísticas (heatmap calendario, evolución mensual)
6. Modo oscuro

## Convenciones
- `VITE_API_URL` en `.env` apunta a `http://localhost:8000`
- JWT en `localStorage` como `access_token`
- Tipos generados con `pnpm run gen:api` desde el OpenAPI del backend (`src/types/api.d.ts`)
- Alias `@/` → `src/`
