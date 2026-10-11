# Plan: base segura y estable antes de la Fase 2

Rama: `feature/base-seguridad-y-calidad`

Objetivo: dejar la app segura, probada y mantenible **antes** de construir nuevas
funciones (calendario, reto semanal, votos, etc.). Nada de la Fase 2 entra en esta rama.

Cada etapa termina en uno o varios commits propios y se puede revisar por separado.
Marca cada casilla cuando esté hecha y verificada.

## Decisiones propuestas (confirmar antes de la Etapa 2)

| Tema | Propuesta | Alternativa |
| --- | --- | --- |
| Cómo se entra | Nombre + contraseña (mínimo 8 caracteres), hash con argon2 | PIN numérico de 6 dígitos (más cómodo, menos seguro) |
| Quién puede registrarse | Solo con **código de invitación** del grupo (`INVITE_CODE`) | Registro abierto con aprobación de un admin |
| Usuarios que ya existen | Quedan sin contraseña y un admin les asigna una clave temporal | Que cada uno cree su clave en el primer login (permite que otra persona la cree antes) |
| Primer admin | `ADMIN_NAMES` solo se aplica al **crear** la cuenta con el código de invitación | Promoverlo a mano en la base de datos |

## Etapa 0: cimientos (antes de tocar la lógica)

- [ ] Pruebas con `pytest` y `TestClient` (base de datos de prueba en PostgreSQL, no SQLite, porque `sync_schema` usa SQL propio de Postgres).
- [ ] Pruebas que fijan el comportamiento actual: login, muro, límite de 2 temas, permisos admin.
- [ ] Alembic con una migración inicial que refleje el esquema actual. Reemplaza a `sync_schema`.
- [ ] CI en GitHub Actions: instalar dependencias y correr las pruebas en cada PR.
- [ ] Fijar la versión de Python (`runtime.txt`).

## Etapa 1: arreglos de seguridad rápidos

- [ ] `SECRET_KEY` obligatoria: la app no arranca en producción si falta o si es la de desarrollo.
- [ ] Cookie de sesión con `https_only` en producción, `same_site="lax"` y `max_age` explícito.
- [ ] Bucle de redirecciones: si el usuario de la sesión ya no existe, limpiar la sesión (`get_usuario_actual`) y que `/` y `/login` no dependan solo de la presencia de la cookie.
- [ ] Cabeceras de seguridad: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`.

## Etapa 2: autenticación real

- [ ] Modelo: columnas `password_hash` y `nombre_normalizado` (minúsculas, sin espacios extra, único). Migración con Alembic.
- [ ] Registro con código de invitación (`INVITE_CODE`) y contraseña con hash argon2.
- [ ] Login con nombre + contraseña. Mensaje de error genérico (no revelar si el nombre existe).
- [ ] `ADMIN_NAMES` deja de promover en cada login. Solo aplica al crear la cuenta.
- [ ] Admin puede restablecer la contraseña de un usuario (clave temporal que se cambia al entrar).
- [ ] Pantalla para que cada usuario cambie su propia contraseña.
- [ ] Límite de intentos fallidos por nombre y por IP, con bloqueo temporal.
- [ ] Token CSRF en todos los formularios POST.
- [ ] Reglas de admin: nadie puede quitar o eliminar al último admin, y un admin no se degrada ni se elimina a sí mismo.
- [ ] Pruebas: suplantación por mayúsculas, fuerza bruta, CSRF, acceso a `/admin` sin rol.

## Etapa 3: bugs y mejoras técnicas

Bugs:
- [ ] Los usuarios pueden borrar sus propios temas (y se corrige el mensaje de error contradictorio).
- [ ] Validar longitudes: nombre ≤ 80, título ≤ 200, sin espacios solo. Mensajes claros en la página.
- [ ] Registro simultáneo con el mismo nombre: capturar el error de `unique` y mostrar mensaje.
- [ ] Límite de 2 temas sin condición de carrera (bloqueo de la fila del usuario o comprobación en la misma transacción).
- [ ] Un título en blanco muestra un aviso.
- [ ] Códigos HTTP correctos (400/403/404) y página de error amigable en lugar de JSON 422 o 500.
- [ ] Eliminar usuario: cascada correcta sobre `Tema` y `RegistroReto`.

Mejoras:
- [ ] Dependencias `require_user` y `require_admin` en lugar de repetir el bloque en cada ruta.
- [ ] Separar `main.py` en routers (`auth`, `muro`, `admin`).
- [ ] Un solo valor para el límite de temas, usado también por la plantilla.
- [ ] Consultas N+1 (`selectinload` o `COUNT` agrupado) en muro y admin.
- [ ] Paginación del muro.
- [ ] `lifespan` en lugar de `on_event`; fechas con zona horaria (UTC) en lugar de `utcnow`.
- [ ] Índice en `temas.usuario_id` y `UniqueConstraint(usuario_id, reto_id)` en `RegistroReto`.
- [ ] Endpoint `/health`.

## Etapa 4: Tailwind compilado

- [ ] Tailwind CLI standalone (sin necesidad de Node) con `tailwind.config.js` que traduce los colores `refugio-*` y las fuentes actuales.
- [ ] `app/static/css/input.css` y salida minificada en `app/static/css/app.css`.
- [ ] Reemplazar el `<script src="https://cdn.tailwindcss.com">` y el bloque `tailwind.config` de `layout.html`.
- [ ] Fuentes Oswald e Inter alojadas en `app/static/fonts` (sin depender de Google Fonts).
- [ ] Script `scripts/build_css.sh` y revisión visual de las 5 pantallas (login, dashboard, muro, admin, menú móvil) antes y después.
- [ ] Decidir si el CSS compilado se versiona en git o se genera en el despliegue de Railway, y reflejarlo en el `Procfile` o en un paso de build.
- [ ] Parámetro de versión en el enlace al CSS para evitar caché antigua.

## Etapa 5: cierre

- [ ] `README.md`: qué es, cómo correrlo en local, variables de entorno, cómo correr pruebas y migraciones, cómo compilar el CSS.
- [ ] `.env.example` actualizado (`SECRET_KEY`, `INVITE_CODE`, `ADMIN_NAMES`, `ENV`).
- [ ] Lista de cambios de despliegue para Railway: variables nuevas, ejecutar `alembic upgrade head`, asignar claves a los usuarios existentes.
- [ ] Revisión final del diff buscando fallos de seguridad y regresiones.

## Variables de entorno nuevas

| Variable | Para qué |
| --- | --- |
| `SECRET_KEY` | Obligatoria en producción |
| `ENV` | `production` activa cookies `https_only` y validaciones estrictas |
| `INVITE_CODE` | Código que el grupo comparte para registrarse |
| `ADMIN_NAMES` | Nombres que se vuelven admin al crear la cuenta |

## Fuera de alcance

Calendario, asistencia, recordatorios, votos, reto semanal, peticiones de oración, PWA y notificaciones push.
Se hacen en ramas posteriores sobre esta base.

## Criterios de terminado

- Las pruebas pasan en CI.
- No se puede entrar como otro usuario sin su contraseña, ni escalar a admin escribiendo un nombre.
- La app no depende de ningún CDN para su estilo.
- Los usuarios existentes pueden volver a entrar con una clave asignada.
- Esquema gestionado solo por Alembic.
