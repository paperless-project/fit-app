# Sincronizar documentación y crear commit

Revisa el estado real del proyecto fit-app, actualiza los documentos (CLAUDE.md, doc/PLAN.md, README.md) y crea un commit. **Los tests deben pasar al 100% antes de hacer cualquier commit.**

## Pasos obligatorios (en orden)

### 1. Ejecutar los tests
```bash
docker compose exec api pytest
```
- Si algún test falla: detente, informa al usuario y NO hagas commit.
- Si todos pasan: anota el número total y continúa.

### 2. Inspeccionar el estado actual del código

Lee los ficheros clave para conocer qué está realmente implementado (no te fíes solo de la memoria):

- `apps/api/src/fitapp/main.py` — routers registrados
- `apps/api/src/fitapp/routers/` — endpoints disponibles
- `apps/api/tests/` — tests existentes (cuenta los ficheros y el total de tests)
- `apps/web/src/App.tsx` — rutas frontend
- `apps/web/src/pages/` — páginas implementadas
- `apps/web/src/lib/` — funciones de API del frontend
- `alembic/versions/` — migraciones aplicadas

### 3. Actualizar CLAUDE.md

Actualiza la sección **"Estado actual"** con:
- Fecha de hoy
- Número real de tests
- Estado de cada fase (marca ✅ las completadas)
- Lista actualizada de endpoints en cada fase
- Bugs conocidos o trabajo pendiente real

### 4. Actualizar doc/PLAN.md

Actualiza:
- Tabla de fases con el estado real (✅ / 🚧 / pendiente)
- Sección **"API REST implementada"** con todos los endpoints actuales
- Número de tests en el pie de la tabla
- Cualquier cambio de arquitectura que se haya tomado

### 5. Actualizar README.md

Actualiza:
- Número de tests en la sección Tests
- Lista de **Funcionalidades implementadas** con todo lo que hay
- Estructura del repositorio si han cambiado ficheros relevantes

### 6. Crear el commit

```bash
# Añadir solo ficheros de documentación y código fuente (nunca .env ni secrets)
git add CLAUDE.md README.md doc/PLAN.md

# Si hay ficheros de código nuevos o modificados sin commitear, añadirlos también
git status  # revisar qué hay pendiente

git commit -m "docs: sincronizar documentación con estado actual — N tests"
```

El mensaje de commit debe reflejar qué fases se han completado desde el último commit de docs.

## Reglas
- **Nunca commitear si los tests no pasan al 100%**
- No inventar funcionalidades: solo documentar lo que existe en el código
- Si hay cambios de código sin commitear además de docs, incluirlos en el mismo commit con un mensaje más descriptivo
- No modificar el código fuente durante este proceso — solo leer y documentar
