from sqlalchemy import func, select

from app.main import MAX_TEMAS_POR_USUARIO
from app.models import Tema


def test_muro_requiere_sesion(client):
    assert client.get("/muro").headers["location"] == "/login"
    assert client.post("/muro", data={"titulo": "x"}).headers["location"] == "/login"


def test_muro_vacio_muestra_mensaje(login):
    c = login("Ana")
    r = c.get("/muro")
    assert r.status_code == 200
    assert "Todavía no hay temas" in r.text


def test_crear_tema_aparece_en_el_muro(login, db):
    c = login("Ana")
    r = c.post("/muro", data={"titulo": "La oracion"})
    assert r.status_code == 303
    assert r.headers["location"] == "/muro"

    r = c.get("/muro")
    assert "La oracion" in r.text
    assert "Ana" in r.text
    assert db.scalar(select(func.count()).select_from(Tema)) == 1


def test_el_muro_muestra_temas_de_otros_usuarios(login):
    login("Ana").post("/muro", data={"titulo": "Tema de Ana"})
    r = login("Luis").get("/muro")
    assert "Tema de Ana" in r.text


def test_limite_de_temas_por_usuario(login, db):
    c = login("Ana")
    for i in range(MAX_TEMAS_POR_USUARIO):
        assert c.post("/muro", data={"titulo": f"Tema {i}"}).status_code == 303

    r = c.post("/muro", data={"titulo": "Uno de mas"})
    assert r.status_code == 200
    assert f"Ya tienes {MAX_TEMAS_POR_USUARIO} temas" in r.text
    assert db.scalar(select(func.count()).select_from(Tema)) == MAX_TEMAS_POR_USUARIO


def test_el_limite_es_por_usuario(login, db):
    for nombre in ("Ana", "Luis"):
        c = login(nombre)
        for i in range(MAX_TEMAS_POR_USUARIO):
            assert c.post("/muro", data={"titulo": f"{nombre} {i}"}).status_code == 303
    assert db.scalar(select(func.count()).select_from(Tema)) == 2 * MAX_TEMAS_POR_USUARIO


def test_titulo_en_blanco_no_crea_tema(login, db):
    c = login("Ana")
    c.post("/muro", data={"titulo": "   "})
    assert db.scalar(select(func.count()).select_from(Tema)) == 0
