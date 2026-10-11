import os

ENV = os.getenv("ENV", "production").strip().lower()
# Estricto por defecto: solo se relaja si se pide de forma explicita.
ES_DESARROLLO = ENV in {"development", "test"}

SECRET_KEYS_DE_EJEMPLO = {"refugio-dev-secret", "cambia-esto-en-produccion"}
SECRET_KEY_LARGO_MINIMO = 32
SECRET_KEY_DESARROLLO = "clave-solo-para-desarrollo-local-no-usar-en-produccion"

SESSION_MAX_AGE = 14 * 24 * 60 * 60  # 14 dias
HSTS_MAX_AGE = 365 * 24 * 60 * 60  # 1 anio


def cargar_secret_key(valor: str | None, es_desarrollo: bool) -> str:
    """Devuelve la clave con la que se firman las cookies de sesion.

    En produccion la clave es obligatoria: si falta o es insegura la app no
    arranca, porque una clave conocida permite falsificar la sesion de
    cualquier usuario.
    """
    valor = (valor or "").strip()
    if es_desarrollo:
        return valor or SECRET_KEY_DESARROLLO

    generar = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'
    if not valor:
        raise RuntimeError(
            "Falta la variable de entorno SECRET_KEY. "
            f"Generala con: {generar} y guardala en las variables de Railway. "
            "Para desarrollo local usa ENV=development."
        )
    if valor in SECRET_KEYS_DE_EJEMPLO:
        raise RuntimeError(
            "SECRET_KEY tiene un valor de ejemplo que es publico. "
            f"Genera una propia con: {generar}"
        )
    if len(valor) < SECRET_KEY_LARGO_MINIMO:
        raise RuntimeError(
            f"SECRET_KEY debe tener al menos {SECRET_KEY_LARGO_MINIMO} caracteres. "
            f"Genera una con: {generar}"
        )
    return valor


SECRET_KEY = cargar_secret_key(os.getenv("SECRET_KEY"), ES_DESARROLLO)
