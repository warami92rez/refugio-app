from sqlalchemy import select

from app.models import Usuario
from tests.conftest import CLAVE


def entrar(client, username="ana", password=CLAVE):
    return client.post("/login", data={"username": username, "password": password})


def test_raiz_sin_sesion_redirige_a_login(client):
    r = client.get("/")
    assert (r.status_code, r.headers["location"]) == (303, "/login")


def test_login_correcto_entra_al_dashboard(client, crear_usuario):
    crear_usuario("Ana")
    r = entrar(client)
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "ANA" in r.text


def test_login_no_distingue_mayusculas_en_el_usuario(client, crear_usuario):
    crear_usuario("Ana")
    r = entrar(client, username="  ANA ")
    assert r.status_code == 303


def test_login_ya_no_crea_cuentas(client, db):
    r = entrar(client, username="nuevo", password="lo-que-sea-123")
    assert r.status_code == 401
    assert db.scalar(select(Usuario).where(Usuario.username == "nuevo")) is None


def test_ya_no_se_puede_entrar_solo_con_el_nombre(client, crear_usuario):
    crear_usuario("Ana")
    r = client.post("/login", data={"nombre": "Ana"})
    assert r.status_code == 401
    assert client.get("/dashboard").headers["location"] == "/login"


def test_clave_incorrecta_y_usuario_inexistente_dan_el_mismo_mensaje(client, crear_usuario):
    crear_usuario("Ana")
    mala = entrar(client, password="clave-equivocada-9")
    inexistente = entrar(client, username="nadie")
    assert mala.status_code == inexistente.status_code == 401
    assert "Usuario o contraseña incorrectos." in mala.text
    assert "Usuario o contraseña incorrectos." in inexistente.text


def test_campos_vacios_o_ausentes_no_rompen(client):
    assert entrar(client, username="", password="").status_code == 401
    assert client.post("/login", data={}).status_code == 401


def test_clave_gigante_se_rechaza_sin_hashear(client, crear_usuario):
    crear_usuario("Ana")
    assert entrar(client, password="x" * 100_000).status_code == 401


def test_usuario_sin_contrasena_no_puede_entrar(client, crear_usuario):
    crear_usuario("Ana", password_hash=None)
    assert entrar(client, password="").status_code == 401
    assert entrar(client, password="cualquier-cosa-1").status_code == 401


def test_dashboard_sin_sesion_redirige_a_login(client):
    r = client.get("/dashboard")
    assert (r.status_code, r.headers["location"]) == (303, "/login")


def test_logout_cierra_la_sesion(client, crear_usuario):
    crear_usuario("Ana")
    entrar(client)
    assert client.post("/logout").status_code == 303
    assert client.get("/dashboard").headers["location"] == "/login"


def test_usuario_desactivado_no_puede_entrar(client, crear_usuario, db):
    crear_usuario("Ana", activo=False)
    r = entrar(client)
    assert r.status_code == 403
    assert "desactivada" in r.text
    assert client.get("/dashboard").headers["location"] == "/login"


def test_desactivado_con_clave_incorrecta_no_revela_su_estado(client, crear_usuario):
    crear_usuario("Ana", activo=False)
    r = entrar(client, password="clave-equivocada-9")
    assert r.status_code == 401
    assert "desactivada" not in r.text


def test_desactivar_cierra_la_sesion_abierta(login, db):
    ana = login("Ana")
    usuario = db.scalar(select(Usuario).where(Usuario.username == "ana"))
    usuario.activo = False
    db.commit()
    r = ana.get("/dashboard")
    assert (r.status_code, r.headers["location"]) == (303, "/login")


def test_nombre_en_admin_names_ya_no_da_rol_admin(client, crear_usuario, db):
    crear_usuario("Directora")
    entrar(client, username="directora")
    assert db.scalar(select(Usuario.rol).where(Usuario.username == "directora")) == "usuario"


def test_el_login_renueva_la_sesion(client, crear_usuario):
    crear_usuario("Ana")
    crear_usuario("Luis")
    entrar(client, username="ana")
    entrar(client, username="luis")
    assert "LUIS" in client.get("/dashboard").text
