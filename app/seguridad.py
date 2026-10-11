import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
_hash_falso = _hasher.hash("contrasena-que-nadie-usa")

ALFABETO_CLAVE_TEMPORAL = "abcdefghjkmnpqrstuvwxyz23456789"  # sin 0/o/1/l/i


def usar_hasher(hasher: PasswordHasher) -> None:
    """Cambia el hasher (las pruebas usan uno barato)."""
    global _hasher, _hash_falso
    _hasher = hasher
    _hash_falso = hasher.hash("contrasena-que-nadie-usa")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(hash_guardado: str | None, password: str) -> bool:
    """Hace el mismo trabajo exista o no el hash, para que el tiempo de respuesta
    no revele si el usuario existe."""
    try:
        _hasher.verify(hash_guardado or _hash_falso, password)
    except (VerificationError, InvalidHashError):
        return False
    return hash_guardado is not None


def necesita_rehash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)


def generar_clave_temporal() -> str:
    grupo = lambda: "".join(secrets.choice(ALFABETO_CLAVE_TEMPORAL) for _ in range(5))  # noqa: E731
    return f"{grupo()}-{grupo()}"
