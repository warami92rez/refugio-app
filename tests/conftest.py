import os

# La configuracion debe fijarse antes de importar la app, porque
# app.database y app.main leen el entorno al importarse.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/refugio_test",
)
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from argon2 import PasswordHasher  # noqa: E402

from app import seguridad  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402

# Hash barato: las pruebas crean muchos usuarios y no necesitan resistir ataques.
seguridad.usar_hasher(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))

CLAVE = "clave-de-prueba-1"


def limpiar_base():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture(autouse=True)
def base_de_datos():
    """Cada prueba parte de una base vacia con el esquema de los modelos."""
    limpiar_base()
    Base.metadata.create_all(bind=engine)
    yield
    limpiar_base()


@pytest.fixture
def db():
    sesion = SessionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def client():
    with TestClient(app, follow_redirects=False) as c:
        yield c


def nuevo_cliente():
    return TestClient(app, follow_redirects=False)


def username_de(nombre: str) -> str:
    return nombre.lower().replace(" ", "_")


@pytest.fixture
def crear_usuario(db):
    """Crea un usuario con contrasena directamente en la base."""

    def _crear(nombre: str, rol: str = "usuario", username: str | None = None, **extra) -> Usuario:
        datos = {"edad": 20, "sede": "Centro", "password_hash": seguridad.hash_password(CLAVE)}
        datos.update(extra)
        usuario = Usuario(nombre=nombre, username=username or username_de(nombre), rol=rol, **datos)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    return _crear


@pytest.fixture
def login(crear_usuario, db):
    """Devuelve una funcion que crea el usuario (si no existe) e inicia sesion con un cliente nuevo."""

    def _login(nombre: str, rol: str = "usuario") -> TestClient:
        username = username_de(nombre)
        if not db.query(Usuario).filter_by(username=username).first():
            crear_usuario(nombre, rol=rol)
        c = nuevo_cliente()
        r = c.post("/login", data={"username": username, "password": CLAVE})
        assert r.status_code == 303 and r.headers["location"] == "/dashboard"
        return c

    return _login
