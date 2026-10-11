from sqlalchemy import select

from app.models import Usuario


def test_raiz_sin_sesion_redirige_a_login(client):
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_crea_cuenta_y_entra_al_dashboard(client, db):
    r = client.post("/login", data={"nombre": "Ana"})
    assert r.status_code == 303
    assert r.headers["location"] == "/dashboard"

    usuario = db.scalar(select(Usuario).where(Usuario.nombre == "Ana"))
    assert usuario is not None
    assert usuario.rol == "usuario"
    assert usuario.activo is True

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "ANA" in r.text


def test_login_no_duplica_usuarios(client, db):
    client.post("/login", data={"nombre": "Ana"})
    client.post("/logout")
    client.post("/login", data={"nombre": "Ana"})
    assert len(db.scalars(select(Usuario)).all()) == 1


def test_login_con_nombre_en_blanco_muestra_error(client):
    r = client.post("/login", data={"nombre": "   "})
    assert r.status_code == 200
    assert "no puede estar vacio" in r.text


def test_dashboard_sin_sesion_redirige_a_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_logout_cierra_la_sesion(client):
    client.post("/login", data={"nombre": "Ana"})
    r = client.post("/logout")
    assert r.status_code == 303
    assert client.get("/dashboard").headers["location"] == "/login"


def test_usuario_desactivado_no_puede_entrar(client, db):
    client.post("/login", data={"nombre": "Ana"})
    client.post("/logout")
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == "Ana"))
    usuario.activo = False
    db.commit()

    r = client.post("/login", data={"nombre": "Ana"})
    assert r.status_code == 200
    assert "desactivada" in r.text


def test_desactivar_cierra_la_sesion_abierta(client, db):
    client.post("/login", data={"nombre": "Ana"})
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == "Ana"))
    usuario.activo = False
    db.commit()

    r = client.get("/dashboard")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_nombre_en_admin_names_recibe_rol_admin(client, db):
    client.post("/login", data={"nombre": "Directora"})
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == "Directora"))
    assert usuario.rol == "admin"
