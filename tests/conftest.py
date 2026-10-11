import os

# La configuracion debe fijarse antes de importar la app, porque
# app.database y app.main leen el entorno al importarse.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/refugio_test",
)
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas"
os.environ["ADMIN_NAMES"] = "Directora"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


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


@pytest.fixture
def login():
    """Devuelve una funcion que inicia sesion (creando la cuenta) con un cliente nuevo."""

    def _login(nombre: str) -> TestClient:
        c = nuevo_cliente()
        r = c.post("/login", data={"nombre": nombre})
        assert r.status_code == 303 and r.headers["location"] == "/dashboard"
        return c

    return _login
