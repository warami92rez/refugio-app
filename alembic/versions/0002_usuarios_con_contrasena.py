"""Usuarios con nombre de usuario, edad, sede y contrasena

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11

Los usuarios que ya existen conservan su cuenta: su nombre de usuario se deriva
de su nombre (sin tildes, en minusculas) y quedan sin contrasena. Un admin les
asigna una clave temporal que deben cambiar al entrar.

`nombre` deja de ser unico: ahora la identidad es `username`.
"""
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

USERNAME_MAX = 30


def _columnas() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("usuarios")}


def username_desde_nombre(nombre: str, id_usuario: int, usados: set[str]) -> str:
    """Deriva un username valido y unico a partir del nombre."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9._]+", "_", sin_tildes.lower()).strip("._")
    base = re.sub(r"_+", "_", base)[: USERNAME_MAX - 6]
    if len(base) < 3:
        base = f"usuario{id_usuario}"

    candidato, n = base, 1
    while candidato in usados:
        n += 1
        candidato = f"{base}{n}"
    usados.add(candidato)
    return candidato


def upgrade() -> None:
    bind = op.get_bind()
    columnas = _columnas()

    if "username" not in columnas:
        op.add_column("usuarios", sa.Column("username", sa.String(30), nullable=True))
    if "edad" not in columnas:
        op.add_column("usuarios", sa.Column("edad", sa.Integer(), nullable=True))
    if "sede" not in columnas:
        op.add_column("usuarios", sa.Column("sede", sa.String(80), nullable=True))
    if "password_hash" not in columnas:
        op.add_column("usuarios", sa.Column("password_hash", sa.String(255), nullable=True))
    if "debe_cambiar_password" not in columnas:
        op.add_column(
            "usuarios",
            sa.Column(
                "debe_cambiar_password", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
        op.alter_column("usuarios", "debe_cambiar_password", server_default=None)

    usuarios = sa.table(
        "usuarios", sa.column("id", sa.Integer), sa.column("nombre", sa.String), sa.column("username", sa.String)
    )
    filas = bind.execute(sa.select(usuarios.c.id, usuarios.c.nombre, usuarios.c.username).order_by(usuarios.c.id)).all()
    usados = {f.username for f in filas if f.username}
    for fila in filas:
        if not fila.username:
            nuevo = username_desde_nombre(fila.nombre, fila.id, usados)
            bind.execute(usuarios.update().where(usuarios.c.id == fila.id).values(username=nuevo))

    op.alter_column("usuarios", "username", nullable=False)

    inspector = sa.inspect(bind)
    for uc in inspector.get_unique_constraints("usuarios"):
        if uc["column_names"] == ["nombre"]:
            op.drop_constraint(uc["name"], "usuarios", type_="unique")
    for ix in inspector.get_indexes("usuarios"):
        if ix.get("unique") and ix["column_names"] == ["nombre"]:
            op.drop_index(ix["name"], table_name="usuarios")
    if not any(uc["column_names"] == ["username"] for uc in inspector.get_unique_constraints("usuarios")):
        op.create_unique_constraint("usuarios_username_key", "usuarios", ["username"])


def downgrade() -> None:
    op.drop_constraint("usuarios_username_key", "usuarios", type_="unique")
    op.create_unique_constraint("usuarios_nombre_key", "usuarios", ["nombre"])
    for columna in ("debe_cambiar_password", "password_hash", "sede", "edad", "username"):
        op.drop_column("usuarios", columna)
