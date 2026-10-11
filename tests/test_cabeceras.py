import pytest

CABECERAS_BASE = {
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


@pytest.mark.parametrize("ruta", ["/login", "/muro", "/dashboard", "/admin", "/"])
def test_cabeceras_de_seguridad_en_todas_las_paginas(client, ruta):
    r = client.get(ruta)
    for nombre, valor in CABECERAS_BASE.items():
        assert r.headers.get(nombre) == valor, f"{nombre} en {ruta}"
    permisos = r.headers.get("permissions-policy", "")
    for recurso in ("camera=()", "microphone=()", "geolocation=()"):
        assert recurso in permisos


def test_paginas_con_sesion_no_se_guardan_en_cache(login):
    c = login("Ana")
    for ruta in ("/dashboard", "/muro", "/login"):
        assert c.get(ruta).headers.get("cache-control") == "no-store"


def test_archivos_estaticos_no_reciben_no_store(client):
    r = client.get("/static/.gitkeep")
    assert r.headers.get("cache-control") != "no-store"
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_hsts_no_se_envia_en_desarrollo(client):
    assert "strict-transport-security" not in client.get("/login").headers


def test_la_cookie_de_sesion_es_httponly_y_lax_con_duracion(client):
    r = client.post("/login", data={"nombre": "Ana"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert f"max-age={14 * 24 * 60 * 60}" in cookie
    assert "secure" not in cookie  # solo en produccion
