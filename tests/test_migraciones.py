"""Verifica que Alembic llega al esquema de los modelos desde cada punto de partida real."""
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.validaciones import USERNAME_RE
from tests.conftest import limpiar_base

RAIZ = Path(__file__).resolve().parent.parent

# Esquema que dejaban create_all + sync_schema antes de usar Alembic (produccion).
ESQUEMA_LEGADO = """
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    rol VARCHAR(20) NOT NULL DEFAULT 'usuario',
    activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE temas (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_creacion TIMESTAMP NOT NULL
);
CREATE TABLE retos_semanales (
    id SERIAL PRIMARY KEY, titulo VARCHAR(200) NOT NULL, descripcion TEXT,
    fecha_inicio TIMESTAMP NOT NULL, fecha_fin TIMESTAMP NOT NULL
);
CREATE TABLE registros_reto (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    reto_id INTEGER NOT NULL REFERENCES retos_semanales(id),
    completado_en TIMESTAMP NOT NULL
);
"""

NOMBRES_DIFICILES = [
    "William",
    "María José",
    "José  Pérez",
    "Ñandú",
    "A",
    "!!!",
    "Ana",
    "ana",
    "ÁÉÍ",
    "😀",
    "x" * 80,
    "Juan.Carlos_Ruiz",
]


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


def crear_esquema_legado(con_datos=True):
    with engine.begin() as conn:
        for sentencia in ESQUEMA_LEGADO.split(";"):
            if sentencia.strip():
                conn.execute(text(sentencia))
        if con_datos:
            for i, nombre in enumerate(NOMBRES_DIFICILES):
                conn.execute(
                    text("INSERT INTO usuarios (nombre, rol, activo) VALUES (:n, :r, :a)"),
                    {"n": nombre, "r": "admin" if i == 0 else "usuario", "a": i != 3},
                )
            conn.execute(
                text("INSERT INTO temas (titulo, usuario_id, fecha_creacion) VALUES ('Oracion', 1, now())")
            )


def test_upgrade_sobre_base_vacia_coincide_con_los_modelos():
    command.upgrade(config(), "head")
    assert diferencias() == []


def test_upgrade_sobre_el_esquema_de_produccion_coincide_con_los_modelos():
    crear_esquema_legado()
    command.upgrade(config(), "head")
    assert diferencias() == []


def test_los_usuarios_existentes_se_conservan_con_username_valido_y_unico():
    crear_esquema_legado()
    command.upgrade(config(), "head")

    with engine.connect() as conn:
        filas = conn.execute(
            text("SELECT id, nombre, username, rol, activo, password_hash, edad, sede, debe_cambiar_password FROM usuarios ORDER BY id")
        ).all()

    assert [f.nombre for f in filas] == NOMBRES_DIFICILES  # ninguno se pierde ni cambia
    usernames = [f.username for f in filas]
    assert len(set(usernames)) == len(usernames)
    for f in filas:
        assert USERNAME_RE.match(f.username), f"{f.nombre!r} -> {f.username!r}"
        assert f.password_hash is None and f.edad is None and f.sede is None
        assert f.debe_cambiar_password is False

    por_nombre = {f.nombre: f for f in filas}
    assert por_nombre["William"].username == "william" and por_nombre["William"].rol == "admin"
    assert por_nombre["María José"].username == "maria_jose"
    assert por_nombre["Ñandú"].username == "nandu"
    assert por_nombre["Ana"].username == "ana" and por_nombre["ana"].username == "ana2"
    assert por_nombre["Ñandú"].activo is False and por_nombre["Ana"].activo is True


def test_los_temas_siguen_ligados_a_su_usuario():
    crear_esquema_legado()
    command.upgrade(config(), "head")
    with engine.connect() as conn:
        fila = conn.execute(
            text("SELECT u.username FROM temas t JOIN usuarios u ON u.id = t.usuario_id")
        ).one()
    assert fila.username == "william"


def test_nombre_deja_de_ser_unico_y_username_si():
    crear_esquema_legado(con_datos=False)
    command.upgrade(config(), "head")
    insertar = "INSERT INTO usuarios (nombre, username, debe_cambiar_password) VALUES (:n, :u, false)"
    with engine.begin() as conn:
        conn.execute(text(insertar), {"n": "Juan", "u": "juan1"})
        conn.execute(text(insertar), {"n": "Juan", "u": "juan2"})  # mismo nombre: ya es valido
    with pytest.raises(Exception):  # mismo username: sigue prohibido
        with engine.begin() as conn:
            conn.execute(text(insertar), {"n": "Otro", "u": "juan1"})


def test_upgrade_agrega_columnas_a_una_tabla_usuarios_muy_antigua():
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE usuarios (id SERIAL PRIMARY KEY, nombre VARCHAR(80) NOT NULL UNIQUE)")
        )
        conn.execute(text("INSERT INTO usuarios (nombre) VALUES ('Ana')"))
    command.upgrade(config(), "head")

    columnas = {c["name"] for c in inspect(engine).get_columns("usuarios")}
    assert {"rol", "activo", "username", "password_hash"} <= columnas
    with engine.connect() as conn:
        fila = conn.execute(text("SELECT rol, activo, username FROM usuarios")).one()
    assert tuple(fila) == ("usuario", True, "ana")
    assert diferencias() == []


def test_upgrade_es_repetible():
    command.upgrade(config(), "head")
    command.upgrade(config(), "head")
    assert diferencias() == []


def test_downgrade_y_upgrade_de_ida_y_vuelta():
    crear_esquema_legado(con_datos=False)
    command.upgrade(config(), "head")
    command.downgrade(config(), "0001")
    assert "username" not in {c["name"] for c in inspect(engine).get_columns("usuarios")}
    command.upgrade(config(), "head")
    assert diferencias() == []
