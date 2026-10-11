import pytest
from sqlalchemy import func, select

from app import cli
from app.models import Usuario
from app.seguridad import verificar_password

CLAVE_ADMIN = "clave-admin-larga-1"
ENTORNO = {
    "BOOTSTRAP_ADMIN_USERNAME": "william",
    "BOOTSTRAP_ADMIN_PASSWORD": CLAVE_ADMIN,
    "BOOTSTRAP_ADMIN_NOMBRE": "William",
}


def get(db, username):
    db.expire_all()
    return db.scalar(select(Usuario).where(Usuario.username == username))


def test_crear_admin_nuevo(db):
    assert "creado" in cli.crear_o_promover_admin(db, "Directora", CLAVE_ADMIN, "Directora Paz")
    u = get(db, "directora")
    assert (u.rol, u.nombre, u.activo, u.debe_cambiar_password) == ("admin", "Directora Paz", True, False)
    assert verificar_password(u.password_hash, CLAVE_ADMIN)


def test_promueve_a_un_usuario_existente_sin_contrasena(db, crear_usuario):
    crear_usuario("William", password_hash=None, activo=False, debe_cambiar_password=True)
    assert "actualizado" in cli.crear_o_promover_admin(db, "william", CLAVE_ADMIN)
    u = get(db, "william")
    assert (u.rol, u.activo, u.debe_cambiar_password, u.nombre) == ("admin", True, False, "William")
    assert verificar_password(u.password_hash, CLAVE_ADMIN)
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1


@pytest.mark.parametrize("username,clave", [("a", CLAVE_ADMIN), ("ok.user", "corta"), ("ok.user", "ok.user")])
def test_crear_admin_rechaza_datos_invalidos(db, username, clave):
    with pytest.raises(cli.ErrorDeComando):
        cli.crear_o_promover_admin(db, username, clave)
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_bootstrap_sin_variables_no_hace_nada(db):
    assert "no se hace nada" in cli.bootstrap_admin(db, {})
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_bootstrap_crea_el_primer_admin(db):
    assert "creado" in cli.bootstrap_admin(db, ENTORNO)
    assert get(db, "william").rol == "admin"


def test_bootstrap_adopta_la_cuenta_existente_del_dueno(db, crear_usuario):
    crear_usuario("William", password_hash=None)
    cli.bootstrap_admin(db, ENTORNO)
    assert get(db, "william").rol == "admin"


def test_bootstrap_no_vuelve_a_actuar_si_ya_hay_admin_con_clave(db, crear_usuario):
    crear_usuario("Directora", rol="admin")
    mensaje = cli.bootstrap_admin(db, ENTORNO)
    assert "ya existe un admin" in mensaje
    assert get(db, "william") is None


def test_bootstrap_no_pisa_la_clave_si_las_variables_se_quedan_puestas(db):
    cli.bootstrap_admin(db, ENTORNO)
    cli.crear_o_promover_admin(db, "william", "clave-nueva-del-admin-2")
    cli.bootstrap_admin(db, ENTORNO)  # siguiente arranque, variables aun definidas
    assert verificar_password(get(db, "william").password_hash, "clave-nueva-del-admin-2")


def test_bootstrap_con_clave_invalida_no_rompe_el_arranque(db):
    mensaje = cli.bootstrap_admin(db, {**ENTORNO, "BOOTSTRAP_ADMIN_PASSWORD": "corta"})
    assert "no se pudo crear" in mensaje
    assert CLAVE_ADMIN not in mensaje


def test_un_usuario_normal_con_clave_no_cuenta_como_admin(db, crear_usuario):
    crear_usuario("Ana")
    assert "creado" in cli.bootstrap_admin(db, ENTORNO)


def test_main_bootstrap_devuelve_cero_aunque_falle(monkeypatch, db):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "w")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "x")
    assert cli.main(["bootstrap-admin"]) == 0


def test_main_crear_admin_lee_la_clave_del_entorno(monkeypatch, db):
    monkeypatch.setenv("CREAR_ADMIN_PASSWORD", CLAVE_ADMIN)
    assert cli.main(["crear-admin", "--username", "directora"]) == 0
    assert get(db, "directora").rol == "admin"


def test_main_crear_admin_con_datos_invalidos_devuelve_error(monkeypatch, db, capsys):
    monkeypatch.setenv("CREAR_ADMIN_PASSWORD", "corta")
    assert cli.main(["crear-admin", "--username", "directora"]) == 1
    assert "Error" in capsys.readouterr().err


def test_main_bootstrap_devuelve_cero_ante_un_error_inesperado(monkeypatch, capsys):
    def falla(*_):
        raise RuntimeError("base de datos caida con datos secretos")

    monkeypatch.setattr(cli, "bootstrap_admin", falla)
    assert cli.main(["bootstrap-admin"]) == 0
    salida = capsys.readouterr().out
    assert "RuntimeError" in salida and "secretos" not in salida
