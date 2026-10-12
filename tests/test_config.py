import os
import subprocess
import sys

import pytest

from app.config import cargar_secret_key

CLAVE_BUENA = "k" * 48


def test_clave_valida_en_produccion():
    assert cargar_secret_key(CLAVE_BUENA, es_desarrollo=False) == CLAVE_BUENA


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_falta_la_clave_en_produccion(valor):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        cargar_secret_key(valor, es_desarrollo=False)


@pytest.mark.parametrize("valor", ["refugio-dev-secret", "cambia-esto-en-produccion"])
def test_valores_de_ejemplo_se_rechazan_en_produccion(valor):
    with pytest.raises(RuntimeError, match="ejemplo"):
        cargar_secret_key(valor, es_desarrollo=False)


def test_clave_corta_se_rechaza_en_produccion():
    with pytest.raises(RuntimeError, match="32"):
        cargar_secret_key("k" * 31, es_desarrollo=False)


def test_en_desarrollo_hay_clave_por_defecto():
    assert len(cargar_secret_key(None, es_desarrollo=True)) >= 32


def test_en_desarrollo_se_respeta_la_clave_dada():
    assert cargar_secret_key("mi-clave", es_desarrollo=True) == "mi-clave"


# --- Arranque real de la app en modo produccion (proceso aparte) ---


def correr(codigo, **entorno):
    env = {k: v for k, v in os.environ.items() if k not in ("ENV", "SECRET_KEY")}
    env.update(entorno)
    return subprocess.run(
        [sys.executable, "-c", codigo], env=env, capture_output=True, text=True, timeout=60
    )


def test_la_app_no_arranca_en_produccion_sin_secret_key():
    r = correr("import app.main")
    assert r.returncode != 0
    assert "SECRET_KEY" in r.stderr


def test_la_app_no_arranca_con_la_clave_publica_antigua():
    r = correr("import app.main", SECRET_KEY="refugio-dev-secret")
    assert r.returncode != 0


CODIGO_PRODUCCION = """
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app, base_url="https://testserver", follow_redirects=False)
r = c.post("/registro", data={"nombre": "Ana", "edad": "20", "username": "ana",
    "sede": "Centro", "password": "una-clave-larga-1", "password2": "una-clave-larga-1"})
assert r.status_code == 303, r.status_code
print("COOKIE:" + r.headers["set-cookie"].lower())
print("HSTS:" + r.headers.get("strict-transport-security", "AUSENTE"))
"""


def test_en_produccion_cookie_secure_y_hsts():
    r = correr(CODIGO_PRODUCCION, SECRET_KEY=CLAVE_BUENA)
    assert r.returncode == 0, r.stderr
    assert "secure" in r.stdout.split("COOKIE:")[1].split("\n")[0]
    assert "HSTS:max-age=31536000" in r.stdout
    assert "includesubdomains" not in r.stdout.lower()
