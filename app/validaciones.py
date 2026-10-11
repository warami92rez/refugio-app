import re
import unicodedata

EDAD_MIN = 10
EDAD_MAX = 99
NOMBRE_MAX = 80
SEDE_MAX = 80
USERNAME_MIN = 3
USERNAME_MAX = 30
PASSWORD_MIN = 8
PASSWORD_MAX = 128

USERNAME_RE = re.compile(rf"^[a-z0-9][a-z0-9._]{{{USERNAME_MIN - 1},{USERNAME_MAX - 1}}}$")


def limpiar_texto(valor: str | None) -> str:
    """Quita caracteres de control y espacios repetidos."""
    valor = "".join(c for c in (valor or "") if c == " " or not unicodedata.category(c).startswith("C"))
    return " ".join(valor.split())


def normalizar_username(valor: str | None) -> str:
    return (valor or "").strip().lower()


def validar_password(password: str | None, username: str = "") -> str | None:
    """Devuelve un mensaje de error, o None si la contraseña es aceptable."""
    password = password or ""
    if len(password) < PASSWORD_MIN:
        return f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres."
    if len(password) > PASSWORD_MAX:
        return f"La contraseña no puede pasar de {PASSWORD_MAX} caracteres."
    if username and password.lower() == username.lower():
        return "La contraseña no puede ser igual al nombre de usuario."
    return None


def validar_registro(form: dict) -> tuple[dict, dict]:
    """Valida el formulario de registro. Devuelve (datos limpios, errores por campo)."""
    errores: dict[str, str] = {}

    nombre = limpiar_texto(form.get("nombre"))
    if not nombre:
        errores["nombre"] = "Escribe tu nombre."
    elif len(nombre) > NOMBRE_MAX:
        errores["nombre"] = f"El nombre no puede pasar de {NOMBRE_MAX} caracteres."

    edad = None
    edad_texto = (form.get("edad") or "").strip()
    if not edad_texto:
        errores["edad"] = "Escribe tu edad."
    elif not edad_texto.isdigit() or not edad_texto.isascii():
        errores["edad"] = "La edad debe ser un número."
    else:
        edad = int(edad_texto)
        if not EDAD_MIN <= edad <= EDAD_MAX:
            errores["edad"] = f"La edad debe estar entre {EDAD_MIN} y {EDAD_MAX} años."
            edad = None

    username = normalizar_username(form.get("username"))
    if not username:
        errores["username"] = "Elige un nombre de usuario."
    elif not USERNAME_RE.match(username):
        errores["username"] = (
            f"Usa de {USERNAME_MIN} a {USERNAME_MAX} caracteres: letras sin tilde, "
            "números, punto o guion bajo, empezando por letra o número."
        )

    sede = limpiar_texto(form.get("sede"))
    if not sede:
        errores["sede"] = "Escribe la sede a la que asistes."
    elif len(sede) > SEDE_MAX:
        errores["sede"] = f"La sede no puede pasar de {SEDE_MAX} caracteres."

    password = form.get("password") or ""
    error_password = validar_password(password, username)
    if error_password:
        errores["password"] = error_password
    elif password != (form.get("password2") or ""):
        errores["password2"] = "Las contraseñas no coinciden."

    datos = {"nombre": nombre, "edad": edad, "username": username, "sede": sede}
    return datos, errores
