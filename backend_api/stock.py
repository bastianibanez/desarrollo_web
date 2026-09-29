from collections import Counter
from fastapi import HTTPException


def demanda_items(conn, items) -> Counter:
    demanda = Counter()
    for item in items:
        if item.producto_id is not None:
            existe = conn.execute(
                "SELECT 1 FROM productos WHERE id = ?", (item.producto_id,)
            ).fetchone()
            if existe is None:
                raise HTTPException(400, "Producto no existe")
            demanda[item.producto_id] += item.cantidad
            continue

        combo = conn.execute(
            "SELECT 1 FROM combos WHERE id = ?", (item.combo_id,)
        ).fetchone()
        if combo is None:
            raise HTTPException(400, "Combo no existe")
        componentes = conn.execute(
            "SELECT producto_id, cantidad FROM lineas_combo WHERE combo_id = ?",
            (item.combo_id,),
        ).fetchall()

        if not componentes:
            raise HTTPException(409, "Combo sin productos")

        for componente in componentes:
            demanda[componente["producto_id"]] += item.cantidad * componente["cantidad"]
    return demanda


def validar_stock(conn, demanda: Counter) -> None:
    for producto_id, cantidad in demanda.items():
        producto = conn.execute(
            "SELECT nombre, stock FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if producto is None or producto["stock"] < cantidad:
            nombre = producto["nombre"] if producto else str(producto_id)
            raise HTTPException(409, f"Stock insuficiente: {nombre}")
