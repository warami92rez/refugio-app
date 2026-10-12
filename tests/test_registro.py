import pytest
from sqlalchemy import func, select

from app.models import Usuario
from tests.conftest import CLAVE

FORM = {
    "nombre": "Ana María",
    "edad": "17",
    "username": "Ana.Maria",
    "sede": "Sede Centro",
    "password": CLAVE,
    "password2": CLAVE,
}


def registrar(client, **cambios):
    return client.post("/registro", data={**FORM, **cambios})


def test_el_formulario_de_registro_se_muestra(client):
    r = client.get("/registro")
    assert r.status_code == 200
    for campo in ("nombre", "edad", "username", "sede", "password", "password2"):
        assert f'name="{campo}"' in r.text


def test_registro_crea_cuenta_normalizada_y_abre_sesion(client, db):
    r = registrar(client)
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")

    u = db.scalar(select(Usuario).where(Usuario.username == "ana.maria"))
    assert (u.nombre, u.edad, u.sede, u.rol, u.activo) == ("Ana María", 17, "Sede Centro", "usuario", True)
    assert u.debe_cambiar_password is False
    assert u.password_hash and CLAVE not in u.password_hash
    assert "ANA MARÍA" in client.get("/dashboard").text


def test_se_puede_entrar_despues_con_el_usuario_registrado(client):
    registrar(client)
    client.post("/logout")
    r = client.post("/login", data={"username": "ana.maria", "password": CLAVE})
    assert r.status_code == 303


def test_registro_nunca_crea_admins(client, db):
    registrar(client, username="admin", nombre="Directora", rol="admin")
    assert db.scalar(select(Usuario.rol).where(Usuario.username == "admin")) == "usuario"


def test_usuario_repetido_ignorando_mayusculas(client, crear_usuario, db):
    crear_usuario("Ana", username="ana.maria")
    r = registrar(client, username="ANA.MARIA")
    assert r.status_code == 400
    assert "ya está en uso" in r.text
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1


def test_dos_personas_pueden_tener_el_mismo_nombre(client, crear_usuario, db):
    crear_usuario("Ana María", username="otra.ana")
    assert registrar(client).status_code == 303
    assert db.scalar(select(func.count()).select_from(Usuario)) == 2


@pytest.mark.parametrize(
    "campo,valor,fragmento",
    [
        ("nombre", "   ", "Escribe tu nombre"),
        ("nombre", "x" * 81, "80 caracteres"),
        ("edad", "", "Escribe tu edad"),
        ("edad", "abc", "debe ser un número"),
        ("edad", "-5", "debe ser un número"),
        ("edad", "9", "entre 10 y 99"),
        ("edad", "100", "entre 10 y 99"),
        ("edad", "１７", "debe ser un número"),
        ("username", "", "Elige un nombre de usuario"),
        ("username", "ab", "3 a 30"),
        ("username", "x" * 31, "3 a 30"),
        ("username", "con espacio", "3 a 30"),
        ("username", "ñandú", "3 a 30"),
        ("username", "_guion", "3 a 30"),
        ("sede", "", "Escribe la sede"),
        ("sede", "s" * 81, "80 caracteres"),
        ("password", "corta", "al menos 8"),
        ("password", "x" * 129, "no puede pasar de 128"),
        ("password2", "otra-clave-123", "no coinciden"),
    ],
)
def test_validaciones_del_registro(client, db, campo, valor, fragmento):
    cambios = {campo: valor}
    if campo == "password":
        cambios["password2"] = valor
    r = registrar(client, **cambios)
    assert r.status_code == 400
    assert fragmento in r.text
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_contrasena_igual_al_usuario_se_rechaza(client):
    r = registrar(client, username="ana.maria", password="ana.maria", password2="ana.maria")
    assert r.status_code == 400
    assert "igual al nombre de usuario" in r.text


def test_error_conserva_lo_escrito_pero_no_las_contrasenas(client):
    r = registrar(client, edad="5", sede="Mi sede")
    assert 'value="Ana María"' in r.text
    assert 'value="Mi sede"' in r.text
    assert CLAVE not in r.text


def test_campos_ausentes_no_dan_error_500(client):
    r = client.post("/registro", data={})
    assert r.status_code == 400


def test_campo_trampa_no_crea_cuenta(client, db):
    r = registrar(client, sitio_web="http://spam.example")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_registro_con_sesion_iniciada_redirige(login):
    assert login("Ana").get("/registro").headers["location"] == "/dashboard"


def test_texto_con_html_se_escapa(client):
    r = registrar(client, nombre="<script>alert(1)</script>", edad="5")
    assert "<script>alert(1)</script>" not in r.text


def test_sedes_sugeridas_solo_si_las_escribieron_dos_personas(client, crear_usuario):
    crear_usuario("Uno", sede="Sede Norte")
    crear_usuario("Dos", sede="sede norte")
    crear_usuario("Tres", sede="Algo privado de una sola persona")
    r = client.get("/registro")
    assert "Sede Norte" in r.text
    assert "privado" not in r.text


def test_sede_sugerida_usa_la_grafia_mas_frecuente(client, crear_usuario):
    for nombre in ("Uno", "Dos"):
        crear_usuario(nombre, sede="sede norte")
    crear_usuario("Tres", sede="Sede Norte")
    html = client.get("/registro").text
    assert '<option value="sede norte">' in html
    assert '<option value="Sede Norte">' not in html


def test_sede_sugerida_en_empate_es_siempre_la_misma(client, crear_usuario):
    # Independiente de la collation de la base de datos (en GitHub no es la misma que en local).
    crear_usuario("Uno", sede="sede norte")
    crear_usuario("Dos", sede="Sede Norte")
    html = client.get("/registro").text
    assert '<option value="Sede Norte">' in html
    assert html.count("<option") == 1


def test_sedes_sugeridas_salen_ordenadas_y_sin_repetir(client, crear_usuario):
    for i, sede in enumerate(["Zeta", "zeta", "alfa", "Alfa", "Medio", "medio"]):
        crear_usuario(f"U{i}", sede=sede)
    html = client.get("/registro").text
    orden = [v for v in ("Alfa", "Medio", "Zeta") if f'<option value="{v}">' in html]
    assert orden == ["Alfa", "Medio", "Zeta"]
    assert html.index('value="Alfa"') < html.index('value="Medio"') < html.index('value="Zeta"')
