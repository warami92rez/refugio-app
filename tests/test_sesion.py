"""Bucle de redirecciones cuando la sesion apunta a un usuario que ya no existe."""
from sqlalchemy import select

from app.models import Usuario


def borrar_usuario(db, nombre):
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == nombre))
    db.delete(usuario)
    db.commit()


def test_sesion_de_usuario_eliminado_no_entra_en_bucle(login, db):
    ana = login("Ana")
    borrar_usuario(db, "Ana")

    r = ana.get("/dashboard")
    assert (r.status_code, r.headers["location"]) == (303, "/login")

    # Antes /login devolvia a /dashboard y quedaba atrapado en un bucle.
    r = ana.get("/login")
    assert r.status_code == 200
    assert "REFUGIO DE PAZ" in r.text


def test_raiz_con_sesion_de_usuario_eliminado_va_a_login(login, db):
    ana = login("Ana")
    borrar_usuario(db, "Ana")

    r = ana.get("/")
    assert (r.status_code, r.headers["location"]) == (303, "/login")


def test_login_despues_de_ser_eliminado_permite_volver_a_entrar(login, db):
    ana = login("Ana")
    borrar_usuario(db, "Ana")

    assert ana.get("/muro").headers["location"] == "/login"
    r = ana.post("/login", data={"nombre": "Ana"})
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")
    assert ana.get("/dashboard").status_code == 200


def test_login_con_sesion_valida_redirige_al_dashboard(login):
    ana = login("Ana")
    r = ana.get("/login")
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")
    r = ana.get("/")
    assert (r.status_code, r.headers["location"]) == (303, "/dashboard")
