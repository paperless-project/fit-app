# Fase 8 — Gestión de cuenta

Implementa la Fase 8 del proyecto fit-app: **Gestión de cuenta** con cambio de contraseña, borrado de cuenta y borrado de actividades individuales.

## Alcance

### Backend (FastAPI)
1. **`PATCH /users/me/password`** — cambio de contraseña
   - Body: `{ current_password, new_password }`
   - Validar contraseña actual con `fastapi-users` password helper
   - Mínimo 8 caracteres para nueva contraseña
   - Respuesta 200 / 400 (contraseña actual incorrecta) / 422

2. **`DELETE /users/me`** — borrado de cuenta
   - Elimina todas las actividades del usuario (cascade) y el usuario
   - Respuesta 204
   - Requiere cabecera de confirmación o body `{ confirm: true }` para evitar borrados accidentales

3. **`DELETE /activities/{id}`** — borrado de actividad individual
   - Solo puede borrar el propietario (verificar `user_id`)
   - Elimina registros asociados (`records`, `laps`) en cascade (ya definido en BD)
   - Respuesta 204 / 403 / 404

### Tests (pytest)
- `test_change_password`: correcto, contraseña actual errónea, nueva < 8 chars
- `test_delete_account`: borra usuario y actividades en cascade, requiere confirmación
- `test_delete_activity`: propietario puede borrar, otro usuario recibe 403, no existente 404
- Todos los tests deben pasar al 100% antes de dar la fase por completada

### Frontend (React + TypeScript)
1. **`AccountPage`** (`/account`) — nueva ruta privada
   - Sección "Cambiar contraseña": formulario con `current_password`, `new_password`, `confirm_password`
   - Sección "Zona de peligro": botón "Borrar cuenta" con modal de confirmación (escribe "BORRAR" para confirmar)
   - Al borrar cuenta: logout automático y redirect a `/login`

2. **Botón "Borrar actividad"** en `ActivityDetailPage`
   - Botón rojo con modal de confirmación
   - Tras borrar: redirect a `/activities`
   - Invalidar caché TanStack Query de la lista

3. **Enlace a `/account`** en el `Layout` (navbar o menú usuario)

## Convenciones del proyecto
- Seguir el stack existente: `fastapi-users`, SQLAlchemy 2.0, TanStack Query, Zustand, Tailwind
- Nunca `Base.metadata.create_all()` — siempre Alembic si hay cambios de esquema (en este caso no hacen falta migraciones)
- Mock de email en tests: `patch("fitapp.auth.users.send_verification_email")`
- Una fase no se da por completada hasta que todos los tests pasen al 100%

## Orden de implementación sugerido
1. Endpoint `DELETE /activities/{id}` + tests
2. Endpoint `PATCH /users/me/password` + tests
3. Endpoint `DELETE /users/me` + tests
4. Frontend: botón borrar en `ActivityDetailPage`
5. Frontend: `AccountPage` completa + enlace en navbar
6. Ejecutar `docker compose exec api pytest` — todos verdes
