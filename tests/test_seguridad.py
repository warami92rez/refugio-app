from app.seguridad import generar_clave_temporal, hash_password, necesita_rehash, verificar_password


def test_hash_y_verificacion():
    h = hash_password("una-clave-larga-1")
    assert h != "una-clave-larga-1" and h.startswith("$argon2")
    assert verificar_password(h, "una-clave-larga-1") is True
    assert verificar_password(h, "otra-clave-larga-1") is False


def test_dos_hashes_de_la_misma_clave_son_distintos():
    assert hash_password("una-clave-larga-1") != hash_password("una-clave-larga-1")


def test_sin_hash_nunca_verifica():
    assert verificar_password(None, "lo-que-sea-123") is False
    assert verificar_password("", "") is False


def test_hash_corrupto_no_lanza_excepcion():
    assert verificar_password("esto-no-es-un-hash", "x") is False


def test_hash_recien_creado_no_necesita_rehash():
    assert necesita_rehash(hash_password("una-clave-larga-1")) is False


def test_clave_temporal_legible_y_distinta():
    claves = {generar_clave_temporal() for _ in range(50)}
    assert len(claves) == 50
    for c in claves:
        assert len(c) == 11 and c[5] == "-"
        assert not set(c.replace("-", "")) & set("01oli")
