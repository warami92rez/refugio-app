"""Comandos de administracion.

    python -m app.cli crear-admin --username william
    python -m app.cli bootstrap-admin

`bootstrap-admin` corre en cada arranque (ver Procfile) y solo actua si no hay
ningun admin con contrasena y estan definidas BOOTSTRAP_ADMIN_USERNAME y
BOOTSTRAP_ADMIN_PASSWORD. Despues de usarse conviene borrar esas variables.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Usuario
from app.seguridad import hash_password
from app.validaciones import USERNAME_RE, limpiar_texto, normalizar_username, validar_password


class ErrorDeComando(Exception):
    pass


def crear_o_promover_admin(db: Session, username: str, password: str, nombre: str | None = None) -> str:
    """Crea un admin, o promueve (y le pone contrasena a) un usuario que ya existe."""
    username = normalizar_username(username)
    if not USERNAME_RE.match(username):
        raise ErrorDeComando("El nombre de usuario no es valido (3 a 30 caracteres: a-z, 0-9, punto o guion bajo).")
    error = validar_password(password, username)
    if error:
        raise ErrorDeComando(error)

    usuario = db.scalar(select(Usuario).where(Usuario.username == username))
    accion = "actualizado"
    if usuario is None:
        nombre_limpio = limpiar_texto(nombre) or username
        usuario = Usuario(nombre=nombre_limpio[:80], username=username)
        db.add(usuario)
        accion = "creado"

    usuario.rol = "admin"
    usuario.activo = True
    usuario.debe_cambiar_password = False
    usuario.password_hash = hash_password(password)
    db.commit()
    return f"Admin '{username}' {accion}."


def bootstrap_admin(db: Session, entorno=os.environ) -> str:
    username = entorno.get("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = entorno.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or not password:
        return "bootstrap-admin: variables no definidas, no se hace nada."

    hay_admin = db.scalar(
        select(Usuario.id).where(Usuario.rol == "admin", Usuario.password_hash.is_not(None)).limit(1)
    )
    if hay_admin:
        return (
            "bootstrap-admin: ya existe un admin con contraseña, no se hace nada. "
            "Puedes borrar BOOTSTRAP_ADMIN_USERNAME y BOOTSTRAP_ADMIN_PASSWORD."
        )
    try:
        return "bootstrap-admin: " + crear_o_promover_admin(
            db, username, password, entorno.get("BOOTSTRAP_ADMIN_NOMBRE")
        )
    except ErrorDeComando as e:
        return f"bootstrap-admin: no se pudo crear el admin: {e}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    crear = sub.add_parser("crear-admin", help="Crea un admin o promueve a un usuario existente")
    crear.add_argument("--username", required=True)
    crear.add_argument("--nombre", help="Nombre para mostrar (solo si el usuario no existe)")
    sub.add_parser("bootstrap-admin", help="Crea el primer admin desde variables de entorno")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.comando == "bootstrap-admin":
            try:
                print(bootstrap_admin(db))
            except Exception as e:  # noqa: BLE001 - nunca debe impedir que la app arranque
                print(f"bootstrap-admin: error inesperado ({type(e).__name__}), se omite.")
            return 0

        password = os.environ.get("CREAR_ADMIN_PASSWORD")
        if password is None:
            password = getpass.getpass("Contraseña: ")
            if password != getpass.getpass("Repite la contraseña: "):
                print("Las contraseñas no coinciden.", file=sys.stderr)
                return 1
        try:
            print(crear_o_promover_admin(db, args.username, password, args.nombre))
        except ErrorDeComando as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
