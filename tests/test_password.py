from sqlalchemy import select

from app.models import Usuario
from tests.conftest import CLAVE

NUEVA = "otra-clave-nueva-2"


def cambiar(cliente, actual=CLAVE, nueva=NUEVA, nueva2=None):
    return cliente.post(
        "/cambiar-password",
        data={"actual": actual, "nueva": nueva, "nueva2": nueva2 if nueva2 is not None else nueva},
    )


def usuario(db, username):
    db.expire_all()
    return db.scalar(select(Usuario).where(Usuario.username == username))


def test_cambiar_password_requiere_sesion(client):
    assert client.get("/cambiar-password").headers["location"] == "/login"
    assert cambiar(client).headers["location"] == "/login"


def test_cambiar_password_correctamente(login, client, db):
    ana = login("Ana")
    r = cambiar(ana)
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")

    ana.post("/logout")
    assert client.post("/login", data={"username": "ana", "password": CLAVE}).status_code == 401
    assert client.post("/login", data={"username": "ana", "password": NUEVA}).status_code == 303


def test_cambiar_password_con_actual_incorrecta(login, db):
    ana = login("Ana")
    r = cambiar(ana, actual="no-es-la-clave-1")
    assert r.status_code == 400
    assert "contraseña actual no es correcta" in r.text


def test_cambiar_password_validaciones(login):
    ana = login("Ana")
    assert "al menos 8" in cambiar(ana, nueva="corta").text
    assert "no coinciden" in cambiar(ana, nueva2="distinta-clave-3").text
    assert "distinta de la actual" in cambiar(ana, nueva=CLAVE).text
    assert "al menos 8" in cambiar(ana, nueva="ana").text


def test_clave_temporal_obliga_a_cambiarla_antes_de_seguir(client, crear_usuario):
    crear_usuario("Ana", debe_cambiar_password=True)
    r = client.post("/login", data={"username": "ana", "password": CLAVE})
    assert r.status_code == 303

    for ruta in ("/dashboard", "/muro", "/admin", "/login", "/registro", "/"):
        r = client.get(ruta)
        assert (r.status_code, r.headers["location"]) == (303, "/cambiar-password"), ruta
    assert client.post("/muro", data={"titulo": "x"}).headers["location"] == "/cambiar-password"

    r = client.get("/cambiar-password")
    assert r.status_code == 200
    assert "clave temporal" in r.text.lower()


def test_tras_cambiar_la_clave_temporal_se_libera_el_acceso(client, crear_usuario, db):
    crear_usuario("Ana", debe_cambiar_password=True)
    client.post("/login", data={"username": "ana", "password": CLAVE})
    assert cambiar(client).headers["location"] == "/dashboard"
    assert usuario(db, "ana").debe_cambiar_password is False
    assert client.get("/muro").status_code == 200


def test_se_puede_salir_con_clave_temporal_pendiente(client, crear_usuario):
    crear_usuario("Ana", debe_cambiar_password=True)
    client.post("/login", data={"username": "ana", "password": CLAVE})
    assert client.post("/logout").headers["location"] == "/login"
    assert client.get("/login").status_code == 200


# --- Restablecer desde el panel admin ---


def test_admin_restablece_clave_y_la_ve_una_sola_vez(login, client, crear_usuario, db):
    admin = login("Directora", rol="admin")
    crear_usuario("Ana", password_hash=None)

    r = admin.post(f"/admin/usuarios/{usuario(db, 'ana').id}/restablecer-password")
    assert r.status_code == 200
    assert "Clave temporal para" in r.text

    u = usuario(db, "ana")
    assert u.password_hash and u.debe_cambiar_password is True

    # La clave mostrada funciona; volver a cargar el panel ya no la muestra.
    import re

    clave = re.search(r"select-all\">([a-z0-9-]+)<", r.text).group(1)
    assert len(clave) == 11
    assert "Clave temporal para" not in admin.get("/admin").text
    assert client.post("/login", data={"username": "ana", "password": clave}).status_code == 303
    assert client.get("/dashboard").headers["location"] == "/cambiar-password"


def test_restablecer_invalida_la_clave_anterior(login, client, crear_usuario, db):
    admin = login("Directora", rol="admin")
    ana = crear_usuario("Ana")
    admin.post(f"/admin/usuarios/{ana.id}/restablecer-password")
    assert client.post("/login", data={"username": "ana", "password": CLAVE}).status_code == 401


def test_restablecer_exige_ser_admin(login, crear_usuario, db):
    otro = crear_usuario("Luis")
    r = login("Ana").post(f"/admin/usuarios/{otro.id}/restablecer-password")
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")
    assert "Clave temporal" not in r.text
    assert usuario(db, "luis").debe_cambiar_password is False


def test_admin_no_se_restablece_a_si_mismo_ni_a_ids_inexistentes(login, db):
    admin = login("Directora", rol="admin")
    yo = usuario(db, "directora")
    assert admin.post(f"/admin/usuarios/{yo.id}/restablecer-password").headers["location"] == "/admin"
    assert admin.post("/admin/usuarios/9999/restablecer-password").headers["location"] == "/admin"
    assert usuario(db, "directora").debe_cambiar_password is False


def test_panel_admin_muestra_edad_sede_y_estado_de_clave(login, crear_usuario):
    admin = login("Directora", rol="admin")
    crear_usuario("Ana", edad=17, sede="Sede Sur", password_hash=None)
    html = admin.get("/admin").text
    assert "@ana" in html and "Sede Sur" in html and "17" in html
    assert "Sin contraseña" in html
