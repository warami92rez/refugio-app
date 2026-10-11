"""Esquema inicial

Revision ID: 0001
Revises:
Create Date: 2026-10-11

Esta migracion es idempotente a proposito: el proyecto ya estaba desplegado
antes de usar Alembic, con tablas creadas por `create_all` y columnas
agregadas por `sync_schema`. Asi `alembic upgrade head` funciona igual sobre
una base vacia, una base creada por la version anterior de la app o una base
que aun no tenia las columnas `rol` y `activo`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _tablas() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columnas(tabla: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(tabla)}


def upgrade() -> None:
    tablas = _tablas()

    if "usuarios" not in tablas:
        op.create_table(
            "usuarios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nombre", sa.String(80), nullable=False, unique=True),
            sa.Column("rol", sa.String(20), nullable=False),
            sa.Column("activo", sa.Boolean(), nullable=False),
        )
    else:
        columnas = _columnas("usuarios")
        if "rol" not in columnas:
            op.add_column(
                "usuarios",
                sa.Column("rol", sa.String(20), nullable=False, server_default="usuario"),
            )
            op.alter_column("usuarios", "rol", server_default=None)
        if "activo" not in columnas:
            op.add_column(
                "usuarios",
                sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
            )
            op.alter_column("usuarios", "activo", server_default=None)

    if "temas" not in tablas:
        op.create_table(
            "temas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("titulo", sa.String(200), nullable=False),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        )

    if "retos_semanales" not in tablas:
        op.create_table(
            "retos_semanales",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("titulo", sa.String(200), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("fecha_inicio", sa.DateTime(), nullable=False),
            sa.Column("fecha_fin", sa.DateTime(), nullable=False),
        )

    if "registros_reto" not in tablas:
        op.create_table(
            "registros_reto",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column(
                "reto_id", sa.Integer(), sa.ForeignKey("retos_semanales.id"), nullable=False
            ),
            sa.Column("completado_en", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("registros_reto")
    op.drop_table("retos_semanales")
    op.drop_table("temas")
    op.drop_table("usuarios")
