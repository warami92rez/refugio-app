import os

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import ES_DESARROLLO, HSTS_MAX_AGE, SECRET_KEY, SESSION_MAX_AGE
from app.database import get_db
from app.models import Tema, Usuario

MAX_TEMAS_POR_USUARIO = 2

ADMIN_NAMES = {
    nombre.strip().lower()
    for nombre in os.getenv("ADMIN_NAMES", "").split(",")
    if nombre.strip()
}

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


def get_usuario_actual(request: Request, db: Session) -> Usuario | None:
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        # La sesion apunta a alguien que ya no existe o fue desactivado.
        request.session.clear()
        return None
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
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_submit(request: Request, nombre: str = Form(...), db: Session = Depends(get_db)):
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "El nombre no puede estar vacio."},
        )

    usuario = db.scalar(select(Usuario).where(Usuario.nombre == nombre_limpio))
    es_admin_configurado = nombre_limpio.lower() in ADMIN_NAMES

    if usuario is None:
        usuario = Usuario(
            nombre=nombre_limpio, rol="admin" if es_admin_configurado else "usuario"
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    elif es_admin_configurado and usuario.rol != "admin":
        usuario.rol = "admin"
        db.commit()

    if not usuario.activo:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Tu cuenta esta desactivada. Contacta a un administrador.",
            },
        )

    request.session["usuario_id"] = usuario.id
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


@app.get("/admin")
def admin_panel(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_actual(request, db)
    if admin is None:
        return RedirectResponse(url="/dashboard", status_code=303)

    usuarios = db.scalars(select(Usuario).order_by(Usuario.nombre)).all()
    temas = db.scalars(select(Tema).order_by(Tema.fecha_creacion.desc())).all()
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "usuario": admin, "usuarios": usuarios, "temas": temas},
    )


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
