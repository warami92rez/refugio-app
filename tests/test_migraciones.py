"""Verifica que Alembic reproduce el esquema de los modelos en los tres escenarios reales."""
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.database import Base, engine
from tests.conftest import limpiar_base

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def base_de_datos():
    """Estas pruebas controlan el esquema ellas mismas: parten de una base vacia."""
    limpiar_base()
    yield
    limpiar_base()


def config() -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    return cfg


def diferencias():
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def test_upgrade_sobre_base_vacia_coincide_con_los_modelos():
    command.upgrade(config(), "head")
    assert diferencias() == []


def test_upgrade_sobre_base_creada_por_la_version_anterior():
    Base.metadata.create_all(bind=engine)
    command.upgrade(config(), "head")
    assert diferencias() == []


def test_upgrade_agrega_columnas_a_una_tabla_usuarios_antigua():
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE usuarios (id SERIAL PRIMARY KEY, nombre VARCHAR(80) NOT NULL UNIQUE)")
        )
        conn.execute(text("INSERT INTO usuarios (nombre) VALUES ('Ana')"))
    command.upgrade(config(), "head")

    columnas = {c["name"] for c in inspect(engine).get_columns("usuarios")}
    assert {"rol", "activo"} <= columnas
    with engine.connect() as conn:
        fila = conn.execute(text("SELECT rol, activo FROM usuarios WHERE nombre = 'Ana'")).one()
    assert tuple(fila) == ("usuario", True)
    assert diferencias() == []


def test_upgrade_es_repetible():
    command.upgrade(config(), "head")
    command.upgrade(config(), "head")
    assert diferencias() == []
