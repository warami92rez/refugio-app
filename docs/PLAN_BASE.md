# Plan: base segura y estable antes de la Fase 2

Rama: `feature/base-seguridad-y-calidad`

Objetivo: dejar la app segura, probada y mantenible **antes** de construir nuevas
funciones (calendario, reto semanal, votos, etc.). Nada de la Fase 2 entra en esta rama.

Cada etapa termina en uno o varios commits propios y se puede revisar por separado.
Marca cada casilla cuando esté hecha y verificada.

## Decisiones tomadas

| Tema | Decisión |
| --- | --- |
| Cómo se entra | **Nombre de usuario + contraseña** (mínimo 8 caracteres, hash con argon2). Sin PIN. |
| Quién puede registrarse | Cualquier persona que complete el formulario de registro. Sin código de invitación ni aprobación previa. |
| Edad | Número entero entre 10 y 99 (confirmado), definido en una constante fácil de cambiar. |
| Formulario de registro | Nombre, edad, nombre de usuario, sede a la que asiste. Se suman contraseña y confirmación, porque sin ellas no hay ingreso con contraseña. |
| Primer admin | Ya no puede depender de un nombre en `ADMIN_NAMES`: con registro abierto, quien registre ese usuario primero sería admin. Se crea con un comando (`python -m app.cli crear-admin`) ejecutado una vez en Railway. |
| Usuarios que ya existen | Conservan su cuenta con el nombre actual como usuario, quedan sin contraseña y un admin les asigna una clave temporal que deben cambiar al entrar. |

## Decisiones propuestas (se pueden cambiar)

| Tema | Propuesta |
| --- | --- |
| Sede | Campo de texto abierto (hasta 80 caracteres), sin lista fija. El formulario sugiere las sedes que ya escribieron otras personas para reducir variaciones de ortografía. |
| Nombre de usuario | De 3 a 30 caracteres: letras, números, punto y guion bajo. Se guarda en minúsculas y es único sin distinguir mayúsculas. |
| Quién ve la edad y la sede | Solo los administradores. El muro muestra el nombre, nunca el usuario, la edad ni la sede. |
| Protección contra registros masivos | Límite de registros por IP, campo trampa oculto y, si hace falta, captcha. |

## Etapa 0: cimientos (antes de tocar la lógica)

- [x] Pruebas con `pytest` y `TestClient` contra PostgreSQL (no SQLite, para probar lo mismo que corre en producción).
- [x] Pruebas que fijan el comportamiento actual: login, muro, límite de 2 temas, permisos admin (35 pruebas).
- [x] Alembic con una migración inicial idempotente (funciona sobre base vacía, base creada por la versión anterior o base sin las columnas `rol`/`activo`). Reemplaza a `sync_schema`; el `Procfile` ejecuta `alembic upgrade head` al arrancar.
- [x] CI en GitHub Actions: instalar dependencias y correr las pruebas en cada PR y en cada push a `main` (`.github/workflows/tests.yml`).
- [x] Fijar la versión de Python (`.python-version`, 3.13).

## Etapa 1: arreglos de seguridad rápidos

- [x] `SECRET_KEY` obligatoria: la app no arranca si falta, mide menos de 32 caracteres o es un valor de ejemplo. El modo estricto es el predeterminado; `ENV=development` lo relaja solo en local (`app/config.py`).
- [x] Cookie de sesión con `https_only` fuera de desarrollo, `same_site="lax"` y `max_age` de 14 días.
- [x] Bucle de redirecciones: si el usuario de la sesión ya no existe, se limpia la sesión (`get_usuario_actual`) y `/` y `/login` ya no dependen solo de la presencia de la cookie.
- [x] Cabeceras de seguridad: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security` (1 año, solo fuera de desarrollo) y `Cache-Control: no-store` en las páginas con sesión. `Content-Security-Policy` queda para la Etapa 4.

## Etapa 2: autenticación real

- [ ] Modelo `Usuario`: `nombre` (para mostrar), `username` (único, normalizado), `edad`, `sede` (texto) y `password_hash`. Migración con Alembic que conserva a los usuarios actuales.
- [ ] Formulario `/registro`: nombre, edad, usuario, sede, contraseña y confirmación. Validaciones en servidor y mensajes claros por campo.
- [ ] Protección del registro abierto: límite por IP, campo trampa oculto y aviso sobre qué datos se guardan y quién los ve.
- [ ] Login con usuario + contraseña. Mensaje de error genérico (no revelar si el usuario existe).
- [ ] Se elimina `ADMIN_NAMES` y el login que crea cuentas. El primer admin se crea con `python -m app.cli crear-admin`.
- [ ] Usuarios existentes: el admin les asigna una clave temporal y la app los obliga a cambiarla al entrar.
- [ ] Admin puede restablecer la contraseña de cualquier usuario (clave temporal que se cambia al entrar).
- [ ] El panel admin muestra edad y sede de cada usuario.
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
- [ ] `.env.example` actualizado (`SECRET_KEY`, `ENV`; se quita `ADMIN_NAMES`).
- [ ] Lista de cambios de despliegue para Railway: variables nuevas, ejecutar `alembic upgrade head`, asignar claves a los usuarios existentes.
- [ ] Revisión final del diff buscando fallos de seguridad y regresiones.

## Antes de fusionar la Etapa 1 a `main`

La Etapa 1 hace que la app no arranque sin `SECRET_KEY`. Si Railway despliega `main` automáticamente, el orden importa:

1. En Railway, servicio de la app, pestaña *Variables*: agregar `SECRET_KEY` con una clave generada con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. No definir `ENV`.
2. Recién después fusionar el PR de la Etapa 1.
3. Verificar que el despliegue arrancó y que se puede iniciar sesión (todos tendrán que volver a entrar una vez).

## Variables de entorno nuevas

| Variable | Para qué |
| --- | --- |
| `SECRET_KEY` | Obligatoria en producción |
| `ENV` | Solo para local: `development` relaja las validaciones. En producción no se define |
| `DATABASE_URL` | Sin cambios |

Se elimina `ADMIN_NAMES`.

## Fuera de alcance

Calendario, asistencia, recordatorios, votos, reto semanal, peticiones de oración, PWA y notificaciones push.
Se hacen en ramas posteriores sobre esta base.

## Criterios de terminado

- Las pruebas pasan en CI.
- No se puede entrar como otro usuario sin su contraseña, ni escalar a admin escribiendo un nombre.
- La app no depende de ningún CDN para su estilo.
- Los usuarios existentes pueden volver a entrar con una clave asignada.
- Esquema gestionado solo por Alembic.
