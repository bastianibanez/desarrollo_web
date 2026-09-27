def test_inicio(client):
    assert client.get("/openapi.json").status_code == 200


def test_categorias_ordenadas(client):
    nombres = [c["nombre"] for c in client.get("/categorias").json()]


def tests_productos_incluyen_categoria(client):
    productos = client.get("/productos").json()
    assert len(productos) == 8
    assert all(p["categoria"] in {"Bowls", "Bebestibles", "Snacks"} for p in productos)
    assert [p["nombre"] for p in productos] == sorted(p["nombre"] for p in productos)


def test_producto_por_id(client):
    p = client.get("/productos/1").json()
    assert p["nombre"] == "Bowl Quinoa"
    assert p["precio"] == 6990
    assert "created_at" in p and "updated_at" in p


def test_producto_inexistente(client):
    r = client.get("/productos/999")
    assert r.status_code == 404
    assert r.json() == {"detail": "No encontrado"}


def test_combos_traen_productos(client):
    combos = client.get("/combos").json()
    assert [c["nombre"] for c in combos] == ["Combo Almuerzo", "Combo Fit"]
    almuerzo = combos[0]

    assert {p["nombre"] for p in almuerzo["productos"]} == {
        "Bowl Quinoa",
        "Jugo Natural Naranja",
    }
    print(all({"id", "nombre", "cantidad"} <= p.keys() for p in almuerzo["productos"]))
    assert all({"id", "nombre", "cantidad"} <= p.keys() for p in almuerzo["productos"])


def test_comunas_con_costo_envio(client):
    comunas = client.get("/comunas").json()
    assert len(comunas) == 9
    providencia = next(c for c in comunas if c["nombre"] == "Providencia")
    assert providencia["costo_envio"] == 1990
    assert providencia["region"] == "Metropolitana"
