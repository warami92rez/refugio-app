import pytest
from sqlalchemy import func, select

from app.models import Tema, Usuario


@pytest.fixture
def admin(login):
    return login("Directora", rol="admin")


def usuario(db, nombre):
    db.expire_all()
    return db.scalar(select(Usuario).where(Usuario.nombre == nombre))


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("get", "/admin"),
        ("post", "/admin/usuarios/1/activar"),
        ("post", "/admin/usuarios/1/desactivar"),
        ("post", "/admin/usuarios/1/promover"),
        ("post", "/admin/usuarios/1/degradar"),
        ("post", "/admin/usuarios/1/eliminar"),
        ("post", "/admin/temas/1/eliminar"),
    ],
)
def test_rutas_admin_rechazan_a_usuarios_normales(login, metodo, ruta):
    c = login("Ana")
    r = getattr(c, metodo)(ruta)
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"


def test_rutas_admin_sin_sesion_no_hacen_nada(client, db, login):
    login("Ana")
    r = client.post("/admin/usuarios/1/eliminar")
    assert r.status_code == 303
    assert usuario(db, "Ana") is not None


def test_admin_ve_el_panel(admin, login):
    login("Ana")
    r = admin.get("/admin")
    assert r.status_code == 200
    assert "PANEL ADMIN" in r.text
    assert "Ana" in r.text


def test_admin_desactiva_y_activa_usuario(admin, login, db):
    login("Ana")
    ana = usuario(db, "Ana")

    admin.post(f"/admin/usuarios/{ana.id}/desactivar")
    assert usuario(db, "Ana").activo is False

    admin.post(f"/admin/usuarios/{ana.id}/activar")
    assert usuario(db, "Ana").activo is True


def test_admin_promueve_y_degrada_usuario(admin, login, db):
    login("Ana")
    ana = usuario(db, "Ana")

    admin.post(f"/admin/usuarios/{ana.id}/promover")
    assert usuario(db, "Ana").rol == "admin"

    admin.post(f"/admin/usuarios/{ana.id}/degradar")
    assert usuario(db, "Ana").rol == "usuario"


def test_admin_no_puede_desactivarse_ni_degradarse_ni_eliminarse(admin, db):
    yo = usuario(db, "Directora")
    admin.post(f"/admin/usuarios/{yo.id}/desactivar")
    admin.post(f"/admin/usuarios/{yo.id}/degradar")
    admin.post(f"/admin/usuarios/{yo.id}/eliminar")

    yo = usuario(db, "Directora")
    assert yo is not None
    assert yo.activo is True
    assert yo.rol == "admin"


def test_admin_elimina_usuario_y_sus_temas(admin, login, db):
    ana = login("Ana")
    ana.post("/muro", data={"titulo": "Tema de Ana"})
    ana_id = usuario(db, "Ana").id

    admin.post(f"/admin/usuarios/{ana_id}/eliminar")

    assert usuario(db, "Ana") is None
    assert db.scalar(select(func.count()).select_from(Tema)) == 0


def test_admin_elimina_un_tema(admin, login, db):
    login("Ana").post("/muro", data={"titulo": "Tema de Ana"})
    tema = db.scalar(select(Tema))

    admin.post(f"/admin/temas/{tema.id}/eliminar")

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Tema)) == 0
    assert usuario(db, "Ana") is not None


def test_acciones_sobre_ids_inexistentes_no_fallan(admin):
    for ruta in (
        "/admin/usuarios/9999/activar",
        "/admin/usuarios/9999/desactivar",
        "/admin/usuarios/9999/promover",
        "/admin/usuarios/9999/degradar",
        "/admin/usuarios/9999/eliminar",
        "/admin/temas/9999/eliminar",
    ):
        assert admin.post(ruta).status_code == 303
