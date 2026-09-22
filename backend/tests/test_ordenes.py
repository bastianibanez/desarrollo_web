import os
import sqlite3

from conftest import CLIENTE


def test_crear_orden_calcula_total_desde_db(client, nueva_orden):
    comuna = next(c for c in client.get("/comunas").json() if c["id"] == 1)
    bowl = client.get("/productos/1").json()
    combo = client.get("/combos").json()[0]

    orden = nueva_orden(
        items=[
            {"producto_id": 1, "cantidad": 2},
            {"combo_id": combo["id"], "cantidad": 1},
        ]
    )

    assert orden["subtotal"] == 2 * bowl["precio"] + combo["precio"]
    assert orden["costo_envio"] == comuna["costo_envio"]
    assert orden["total"] == orden["subtotal"] + orden["costo_envio"]


def test_detalle_de_orden(client, nueva_orden):
    orden = nueva_orden()
    detalle = client.get(f"/ordenes/{orden['id']}").json()
    assert detalle["rut"] == "12345678-5"  # normalizado: sin puntos
    assert detalle["nombres"] == "Ana María"
    assert detalle["comuna"] == "Providencia"
    assert detalle["estado"] == "pendiente"
    assert detalle["lineas"] == [
        {"producto_id": 1, "combo_id": None, "cantidad": 1, "precio_unitario": 6990}
    ]


def test_orden_inexistente_404(client):
    r = client.get("/ordenes/999")
    assert r.status_code == 404
    assert r.json() == {
        "detail": "No encontrado"
    }  # el nuestro, no el "Not Found" genérico


def test_mismo_rut_reutiliza_cliente(client, nueva_orden):
    nueva_orden()
    nueva_orden(cliente={**CLIENTE, "rut": "12345678-5"})  # sin puntos
    nueva_orden(cliente={**CLIENTE, "rut": "12.345.678-5"})  # con puntos otra vez

    conn = sqlite3.connect(os.environ["TIENDA_DB"])
    (clientes,) = conn.execute(
        "SELECT COUNT(*) FROM clientes WHERE rut = '12345678-5'"
    ).fetchone()
    conn.close()
    assert clientes == 1


def test_item_sin_producto_ni_combo_422(client):
    r = client.post(
        "/ordenes",
        json={
            "cliente": CLIENTE,
            "direccion": {"calle": "C", "numero": "1", "comuna_id": 1},
            "items": [{"cantidad": 1}],
        },
    )
    assert r.status_code == 422


def test_item_con_ambos_422(client):
    r = client.post(
        "/ordenes",
        json={
            "cliente": CLIENTE,
            "direccion": {"calle": "C", "numero": "1", "comuna_id": 1},
            "items": [{"producto_id": 1, "combo_id": 1, "cantidad": 1}],
        },
    )
    assert r.status_code == 422


def test_sin_items_422(client):
    r = client.post(
        "/ordenes",
        json={
            "cliente": CLIENTE,
            "direccion": {"calle": "C", "numero": "1", "comuna_id": 1},
            "items": [],
        },
    )
    assert r.status_code == 422


def test_comuna_sin_despacho_400(client):
    r = client.post(
        "/ordenes",
        json={
            "cliente": CLIENTE,
            "direccion": {"calle": "C", "numero": "1", "comuna_id": 999},
            "items": [{"producto_id": 1, "cantidad": 1}],
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "No hay despacho a esa comuna"


def test_producto_inexistente_400(client):
    r = client.post(
        "/ordenes",
        json={
            "cliente": CLIENTE,
            "direccion": {"calle": "C", "numero": "1", "comuna_id": 1},
            "items": [{"producto_id": 999, "cantidad": 1}],
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Producto no existe"
