import os

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, engine, get_db
from app.models import Tema, Usuario

app = FastAPI(title="Refugio App")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "refugio-dev-secret"))
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


def get_usuario_actual(request: Request, db: Session) -> Usuario | None:
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    return db.get(Usuario, usuario_id)


@app.get("/")
def index(request: Request):
    if request.session.get("usuario_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login")
def login_form(request: Request):
    if request.session.get("usuario_id"):
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
    if usuario is None:
        usuario = Usuario(nombre=nombre_limpio)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

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
    return templates.TemplateResponse(
        "muro.html", {"request": request, "usuario": usuario, "temas": temas}
    )


@app.post("/muro")
def crear_tema(request: Request, titulo: str = Form(...), db: Session = Depends(get_db)):
    usuario = get_usuario_actual(request, db)
    if usuario is None:
        return RedirectResponse(url="/login", status_code=303)

    titulo_limpio = titulo.strip()
    if titulo_limpio:
        tema = Tema(titulo=titulo_limpio, usuario_id=usuario.id)
        db.add(tema)
        db.commit()

    return RedirectResponse(url="/muro", status_code=303)
