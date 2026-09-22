NUEVO = {"nombre": "Té Verde", "precio": 1800, "stock": 5, "categoria_id": 2}


def test_crear_producto(client):
    r = client.post("/productos", json=NUEVO)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Té Verde"
    assert body["descripcion"] is None
    assert "id" in body and "created_at" in body
    assert client.get(f"/productos/{body['id']}").status_code == 200


def test_crear_incompleto_422(client):
    r = client.post("/productos", json={"nombre": "Sin precio"})
    assert r.status_code == 422
    faltantes = {e["loc"][-1] for e in r.json()["detail"]}
    assert faltantes == {"precio", "stock", "categoria_id"}


def test_precio_negativo_422(client):
    assert client.post("/productos", json={**NUEVO, "precio": -1}).status_code == 422


def test_actualizar_producto(client):
    pid = client.post("/productos", json=NUEVO).json()["id"]
    r = client.put(
        f"/productos/{pid}",
        json={**NUEVO, "precio": 1900, "descripcion": "Hojas sueltas"},
    )
    assert r.status_code == 200
    assert r.json()["precio"] == 1900
    assert r.json()["descripcion"] == "Hojas sueltas"
    assert client.put("/productos/999", json=NUEVO).status_code == 404


def test_eliminar_producto(client):
    pid = client.post("/productos", json=NUEVO).json()["id"]
    assert client.delete(f"/productos/{pid}").json() == {"ok": True}
    assert client.get(f"/productos/{pid}").status_code == 404
    assert client.delete(f"/productos/{pid}").status_code == 404


def test_no_se_puede_borrar_producto_en_combo(client):
    # El producto 1 (Bowl Quinoa) está en el Combo Almuerzo → la FK lo impide
    r = client.delete("/productos/1")
    assert r.status_code == 409
    assert "FOREIGN KEY" in r.json()["detail"]
    assert client.get("/productos/1").status_code == 200  # sigue existiendo
