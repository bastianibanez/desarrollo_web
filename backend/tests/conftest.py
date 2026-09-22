import os

import pytest
from fastapi.testclient import TestClient

CLIENTE = {
    "nombres": "Ana María",
    "apellidos": "García",
    "rut": "12.345.678-5",
    "email": "ana@ejemplo.cl",
}


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    os.environ["TIENDA_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def nueva_orden(client):
    """Crea orden válida y devuelve JSON de respuesta"""

    def _crear(**cambios):
        body = {
            "cliente": CLIENTE,
            "direccion": {"calle": "Calle 1", "numero": "10", "comuna_id": 1},
            "items": [{"producto_id": 1, "cantidad": 1}],
        }
        body.update(cambios)
        r = client.post("/ordenes", json=body)
        assert r.status_code == 201, r.text
        return r.json()

    return _crear
