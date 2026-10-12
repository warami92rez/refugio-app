from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import ES_DESARROLLO, HSTS_MAX_AGE, SECRET_KEY, SESSION_MAX_AGE
from app.database import get_db
from app.models import Tema, Usuario
from app.seguridad import (
    generar_clave_temporal,
    hash_password,
    necesita_rehash,
    verificar_password,
)
from app.validaciones import (
    PASSWORD_MAX,
    normalizar_username,
    validar_password,
    validar_registro,
)

MAX_TEMAS_POR_USUARIO = 2

app = FastAPI(title="Refugio de Paz")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=not ES_DESARROLLO,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

CABECERAS_DE_SEGURIDAD = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
if not ES_DESARROLLO:
    CABECERAS_DE_SEGURIDAD["Strict-Transport-Security"] = f"max-age={HSTS_MAX_AGE}"


@app.middleware("http")
async def agregar_cabeceras_de_seguridad(request: Request, call_next):
    response = await call_next(request)
    for nombre, valor in CABECERAS_DE_SEGURIDAD.items():
        response.headers[nombre] = valor
    if not request.url.path.startswith("/static"):
        # Las paginas dependen de la sesion: que el navegador no las guarde.
        response.headers["Cache-Control"] = "no-store"
    return response


class RedirigirA(Exception):
    """Corta la peticion actual y redirige (se usa desde get_usuario_actual)."""

    def __init__(self, url: str):
        self.url = url


@app.exception_handler(RedirigirA)
async def redirigir(request: Request, exc: RedirigirA):
    return RedirectResponse(url=exc.url, status_code=303)


def get_usuario_actual(
    request: Request, db: Session, permitir_cambio_pendiente: bool = False
) -> Usuario | None:
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        # La sesion apunta a alguien que ya no existe o fue desactivado.
        request.session.clear()
        return None
    if usuario.debe_cambiar_password and not permitir_cambio_pendiente:
        raise RedirigirA("/cambiar-password")
    return usuario


def get_admin_actual(request: Request, db: Session) -> Usuario | None:
    usuario = get_usuario_actual(request, db)
    if usuario is None or usuario.rol != "admin":
        return None
    return usuario


def contar_temas_usuario(db: Session, usuario_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Tema).where(Tema.usuario_id == usuario_id)
    )


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    if get_usuario_actual(request, db):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    if get_usuario_actual(request, db):
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_login(request)


def render_login(request: Request, error: str | None = None, username: str = "", status_code: int = 200):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error, "username": username},
        status_code=status_code,
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    username_n = normalizar_username(username)
    usuario = db.scalar(select(Usuario).where(Usuario.username == username_n)) if username_n else None

    # Mensaje unico para usuario inexistente, sin contrasena o clave incorrecta.
    clave_ok = len(password) <= PASSWORD_MAX and verificar_password(
        usuario.password_hash if usuario else None, password
    )
    if not clave_ok:
        return render_login(request, "Usuario o contraseña incorrectos.", username_n, 401)

    if not usuario.activo:
        return render_login(
            request, "Tu cuenta está desactivada. Contacta a un administrador.", username_n, 403
        )

    if necesita_rehash(usuario.password_hash):
        usuario.password_hash = hash_password(password)
        db.commit()

    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return RedirectResponse(url="/dashboard", status_code=303)


def sedes_sugeridas(db: Session) -> list[str]:
    """Sedes escritas por al menos 2 personas (evita mostrar texto suelto de uno solo).

    Las variantes de mayusculas se agrupan y se sugiere la grafia mas usada; en empate
    gana la primera en orden alfabetico. Se resuelve aqui y no en SQL para que el
    resultado no dependa de la collation de la base de datos.
    """
    filas = db.execute(
        select(Usuario.sede, func.count())
        .where(Usuario.sede.is_not(None))
        .group_by(Usuario.sede)
        .order_by(func.count().desc())
        .limit(1000)
    ).all()

    grupos: dict[str, list[tuple[str, int]]] = {}
    for sede, cantidad in filas:
        grupos.setdefault(sede.casefold(), []).append((sede, cantidad))

    sugeridas = []
    for variantes in grupos.values():
        if sum(c for _, c in variantes) >= 2:
            sugeridas.append(min(variantes, key=lambda v: (-v[1], v[0]))[0])
    return sorted(sugeridas, key=lambda s: (s.casefold(), s))[:30]


def render_registro(request: Request, db: Session, valores=None, errores=None, status_code=200):
    return templates.TemplateResponse(
        "registro.html",
        {
            "request": request,
            "valores": valores or {},
            "errores": errores or {},
            "sedes": sedes_sugeridas(db),
        },
        status_code=status_code,
    )


@app.get("/registro")
def registro_form(request: Request, db: Session = Depends(get_db)):
    if get_usuario_actual(request, db):
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_registro(request, db)


@app.post("/registro")
def registro_submit(
    request: Request,
    nombre: str = Form(""),
    edad: str = Form(""),
    username: str = Form(""),
    sede: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    sitio_web: str = Form(""),  # campo trampa: las personas no lo ven, los bots lo llenan
    db: Session = Depends(get_db),
):
    if sitio_web:
        return RedirectResponse(url="/login", status_code=303)

    datos, errores = validar_registro(
        {
            "nombre": nombre,
            "edad": edad,
            "username": username,
            "sede": sede,
            "password": password,
            "password2": password2,
        }
    )
    ya_usado = "Ese nombre de usuario ya está en uso."
    if "username" not in errores and db.scalar(
        select(Usuario.id).where(Usuario.username == datos["username"])
    ):
        errores["username"] = ya_usado

    usuario = None
    if not errores:
        usuario = Usuario(**datos, password_hash=hash_password(password), rol="usuario")
        db.add(usuario)
        try:
            db.commit()
        except IntegrityError:  # dos registros simultaneos con el mismo usuario
            db.rollback()
            errores["username"] = ya_usado

    if errores:
        return render_registro(request, db, valores=datos | {"edad": edad}, errores=errores, status_code=400)

    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return RedirectResponse(url="/dashboard", status_code=303)


def render_cambiar_password(request: Request, usuario: Usuario, error=None, status_code=200):
    return templates.TemplateResponse(
        "cambiar_password.html",
        {"request": request, "usuario": usuario, "error": error, "forzado": usuario.debe_cambiar_password},
        status_code=status_code,
    )


@app.get("/cambiar-password")
def cambiar_password_form(request: Request, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(request, db, permitir_cambio_pendiente=True)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)
    return render_cambiar_password(request, usuario)


@app.post("/cambiar-password")
def cambiar_password_submit(
    request: Request,
    actual: str = Form(""),
    nueva: str = Form(""),
    nueva2: str = Form(""),
    db: Session = Depends(get_db),
):
    usuario = get_usuario_actual(request, db, permitir_cambio_pendiente=True)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)

    error = None
    if len(actual) > PASSWORD_MAX or not verificar_password(usuario.password_hash, actual):
        error = "La contraseña actual no es correcta."
    elif validar_password(nueva, usuario.username):
        error = validar_password(nueva, usuario.username)
    elif nueva != nueva2:
        error = "Las contraseñas nuevas no coinciden."
    elif nueva == actual:
        error = "La contraseña nueva debe ser distinta de la actual."
    if error:
        return render_cambiar_password(request, usuario, error, 400)

    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_password = False
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(request, db)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "usuario": usuario}
    )


@app.get("/muro")
def muro(request: Request, db: Session = Depends(get_db)):
    usuario = get_usuario_actual(request, db)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)

    temas = db.scalars(select(Tema).order_by(Tema.fecha_creacion.desc())).all()
    mis_temas = contar_temas_usuario(db, usuario.id)
    return templates.TemplateResponse(
        "muro.html",
        {"request": request, "usuario": usuario, "temas": temas, "mis_temas": mis_temas},
    )


@app.post("/muro")
def crear_tema(request: Request, titulo: str = Form(...), db: Session = Depends(get_db)):
    usuario = get_usuario_actual(request, db)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)

    titulo_limpio = titulo.strip()
    mis_temas = contar_temas_usuario(db, usuario.id)

    error = None
    if titulo_limpio and mis_temas >= MAX_TEMAS_POR_USUARIO:
        error = f"Ya tienes {MAX_TEMAS_POR_USUARIO} temas propuestos. Elimina uno antes de agregar otro."
    elif titulo_limpio:
        tema = Tema(titulo=titulo_limpio, usuario_id=usuario.id)
        db.add(tema)
        db.commit()
        mis_temas += 1

    if error:
        temas = db.scalars(select(Tema).order_by(Tema.fecha_creacion.desc())).all()
        return templates.TemplateResponse(
            "muro.html",
            {
                "request": request,
                "usuario": usuario,
                "temas": temas,
                "mis_temas": mis_temas,
                "error": error,
            },
        )

    return RedirectResponse(url="/muro", status_code=303)


def render_admin(request: Request, db: Session, admin: Usuario, **extra):
    usuarios = db.scalars(select(Usuario).order_by(Usuario.nombre, Usuario.username)).all()
    temas = db.scalars(select(Tema).order_by(Tema.fecha_creacion.desc())).all()
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "usuario": admin, "usuarios": usuarios, "temas": temas, **extra},
    )


@app.get("/admin")
def admin_panel(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_admin(request, db, admin)


@app.post("/admin/usuarios/{usuario_id}/restablecer-password")
def admin_restablecer_password(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    objetivo = db.get(Usuario, usuario_id)
    if objetivo is None or objetivo.id == admin.id:
        return RedirectResponse(url="/admin", status_code=303)

    clave = generar_clave_temporal()
    objetivo.password_hash = hash_password(clave)
    objetivo.debe_cambiar_password = True
    db.commit()
    # La clave temporal se muestra una sola vez, en esta respuesta; no se guarda en claro.
    return render_admin(request, db, admin, clave_temporal=clave, usuario_clave=objetivo)


@app.post("/admin/usuarios/{usuario_id}/activar")
def admin_activar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    objetivo = db.get(Usuario, usuario_id)
    if objetivo:
        objetivo.activo = True
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/usuarios/{usuario_id}/desactivar")
def admin_desactivar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    if usuario_id != admin.id:
        objetivo = db.get(Usuario, usuario_id)
        if objetivo:
            objetivo.activo = False
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/usuarios/{usuario_id}/promover")
def admin_promover_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    objetivo = db.get(Usuario, usuario_id)
    if objetivo:
        objetivo.rol = "admin"
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/usuarios/{usuario_id}/degradar")
def admin_degradar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    if usuario_id != admin.id:
        objetivo = db.get(Usuario, usuario_id)
        if objetivo:
            objetivo.rol = "usuario"
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/usuarios/{usuario_id}/eliminar")
def admin_eliminar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    if usuario_id != admin.id:
        objetivo = db.get(Usuario, usuario_id)
        if objetivo:
            db.query(Tema).filter(Tema.usuario_id == usuario_id).delete()
            db.delete(objetivo)
            db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/temas/{tema_id}/eliminar")
def admin_eliminar_tema(tema_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    tema = db.get(Tema, tema_id)
    if tema:
        db.delete(tema)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)
