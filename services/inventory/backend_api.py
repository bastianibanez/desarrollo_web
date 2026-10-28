from collections import Counter
from typing import Literal

from fastapi import Request
from pydantic import Field

from services import seeds
from services.common import (
    MAX_MONEY,
    Context,
    application,
    fail,
    later,
    money,
    now,
    page,
    pagination,
)
from services.dto import DTO, Item, Producto


class ReservaIn(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    items: list[Item] = Field(min_length=1, max_length=50)
    limite_subtotal: int = Field(default=MAX_MONEY, ge=0, le=MAX_MONEY)


class Referencia(DTO):
    tipo: Literal["producto", "combo"]
    id: int = Field(gt=0)


class Consulta(DTO):
    items: list[Referencia] = Field(max_length=50)


class AccionReserva(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    orden_id: int = Field(gt=0)
    motivo: str = Field(default="Operación autorizada", min_length=1, max_length=1000)


def seed(ctx):
    with ctx.transaction() as db:
        if db.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]:
            return
        for name in seeds.CATEGORIAS:
            db.execute("INSERT INTO categorias(nombre) VALUES(?)", (name,))
        for name, description, price, stock, category in seeds.PRODUCTOS:
            category_id = db.execute(
                "SELECT id FROM categorias WHERE nombre=?", (category,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO productos(nombre,descripcion,precio,precio_oferta,stock,categoria_id) VALUES(?,?,?,?,?,?)",
                (
                    name,
                    description,
                    price,
                    seeds.OFERTAS_PRODUCTOS.get(name),
                    stock,
                    category_id,
                ),
            )
        for name, description, price, lines in seeds.COMBOS:
            id = db.execute(
                "INSERT INTO combos(nombre,descripcion,precio,precio_oferta) VALUES(?,?,?,?)",
                (name, description, price, seeds.OFERTAS_COMBOS.get(name)),
            ).lastrowid
            for product, qty in lines:
                product_id = db.execute(
                    "SELECT id FROM productos WHERE nombre=?", (product,)
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO lineas_combo(combo_id,producto_id,cantidad) VALUES(?,?,?)",
                    (id, product_id, qty),
                )


def free_stock(db):
    rows = db.execute(
        """SELECT d.producto_id,SUM(d.cantidad) AS cantidad FROM detalles_reserva d
      JOIN reservas r ON r.id=d.reserva_id WHERE r.estado='activa' AND r.vence_en>? GROUP BY d.producto_id""",
        (now(),),
    ).fetchall()
    reserved = {r["producto_id"]: r["cantidad"] for r in rows}
    return {
        r["id"]: r["stock"] - reserved.get(r["id"], 0)
        for r in db.execute("SELECT id,stock FROM productos")
    }


def offers(user):
    return user is not None and (
        user["rol"] in {"administrador", "dueno"}
        or (user["rol"] == "cliente" and user["email_verificado_at"])
    )


def catalog(db, user):
    available = free_stock(db)
    products = {}
    for row in db.execute(
        "SELECT p.*,c.nombre AS categoria FROM productos p JOIN categorias c ON c.id=p.categoria_id"
    ):
        p = dict(row)
        if not offers(user):
            p["precio_oferta"] = None
        p["precio_final"] = (
            p["precio_oferta"] if p["precio_oferta"] is not None else p["precio"]
        )
        p["disponible"] = bool(p["activo"] and available[p["id"]] > 0)
        p["activo"] = bool(p["activo"])
        if not user or user["rol"] not in {"administrador", "dueno"}:
            p.pop("stock")
        products[p["id"]] = p
    components = {}
    for row in db.execute(
        "SELECT lc.combo_id,lc.producto_id,lc.cantidad,p.nombre,p.activo FROM lineas_combo lc JOIN productos p ON p.id=lc.producto_id"
    ):
        components.setdefault(row["combo_id"], []).append(dict(row))
    combos = {}
    for row in db.execute("SELECT * FROM combos"):
        c = dict(row)
        if not offers(user):
            c["precio_oferta"] = None
        c["precio_final"] = (
            c["precio_oferta"] if c["precio_oferta"] is not None else c["precio"]
        )
        comp = components.get(c["id"], [])
        c["disponible"] = bool(comp) and all(
            x["activo"] and available[x["producto_id"]] >= x["cantidad"] for x in comp
        )
        c["productos"] = [
            {"id": x["producto_id"], "nombre": x["nombre"], "cantidad": x["cantidad"]}
            for x in comp
        ]
        combos[c["id"]] = c
    return products, combos


def reservation(db, id):
    row = db.execute("SELECT * FROM reservas WHERE id=?", (id,)).fetchone()
    if not row:
        fail(404, "Reserva no encontrada")
    result = dict(row)
    if result["estado"] == "activa" and result["vence_en"] <= now():
        db.execute(
            "UPDATE reservas SET estado='expirada',version=version+1 WHERE id=? AND estado='activa'",
            (id,),
        )
        result["estado"] = "expirada"
    result["lineas"] = [
        {**dict(x), "subtotal": x["cantidad"] * x["precio_unitario"]}
        for x in db.execute(
            "SELECT producto_id,combo_id,nombre,cantidad,precio_unitario FROM lineas_reserva WHERE reserva_id=? ORDER BY posicion",
            (id,),
        )
    ]
    result["moneda"] = "CLP"
    return result


def create_app(ctx=None):
    ctx = ctx or Context("inventory")
    app = application(ctx, startup=seed)

    async def reader(request):
        ctx.require_caller(request, "graphql")
        return await ctx.actor(request, optional=True)

    @app.get("/categorias")
    async def categories(request: Request):
        await reader(request)
        with ctx.read() as db:
            return [
                dict(x)
                for x in db.execute("SELECT * FROM categorias ORDER BY nombre,id")
            ]

    @app.get("/productos")
    async def products(
        request: Request,
        pagina: int = 1,
        limite: int = 12,
        producto_id: int | None = None,
        categoria_id: int | None = None,
        busqueda: str = "",
        solo_disponibles: bool = False,
        incluir_inactivos: bool = False,
    ):
        user = await reader(request)
        offset = pagination(pagina, limite)
        if len(busqueda) > 100:
            fail(422, "Búsqueda demasiado larga")
        if incluir_inactivos and (
            not user or user["rol"] not in {"administrador", "dueno"}
        ):
            fail(403, "Filtro administrativo no autorizado")
        with ctx.read() as db:
            values = list(catalog(db, user)[0].values())
        values = [
            p
            for p in values
            if (p["activo"] or incluir_inactivos)
            and (producto_id is None or p["id"] == producto_id)
            and (categoria_id is None or p["categoria_id"] == categoria_id)
            and (not solo_disponibles or p["disponible"])
            and busqueda.casefold().strip()
            in (p["nombre"] + " " + (p["descripcion"] or "")).casefold()
        ]
        values.sort(key=lambda p: (p["nombre"], p["id"]))
        return page(values[offset : offset + limite], len(values), pagina, limite)

    @app.get("/productos/{id}")
    async def product(id: int, request: Request):
        user = await reader(request)
        with ctx.read() as db:
            p = catalog(db, user)[0].get(id)
        if not p or not p["activo"]:
            fail(404, "Producto no encontrado")
        return p

    @app.get("/combos")
    async def combos(
        request: Request,
        pagina: int = 1,
        limite: int = 12,
        combo_id: int | None = None,
        busqueda: str = "",
        solo_disponibles: bool = False,
    ):
        user = await reader(request)
        offset = pagination(pagina, limite)
        if len(busqueda) > 100:
            fail(422, "Búsqueda demasiado larga")
        with ctx.read() as db:
            values = list(catalog(db, user)[1].values())
        values = [
            p
            for p in values
            if (combo_id is None or p["id"] == combo_id)
            and (not solo_disponibles or p["disponible"])
            and busqueda.casefold().strip()
            in (p["nombre"] + " " + (p["descripcion"] or "")).casefold()
        ]
        values.sort(key=lambda p: (p["nombre"], p["id"]))
        return page(values[offset : offset + limite], len(values), pagina, limite)

    async def write_product(request, body, id=None):
        ctx.require_caller(request, "gateway")
        actor = await ctx.actor(request, {"administrador", "dueno"})
        async with ctx.operation(
            request, f"producto:{id or 'nuevo'}", actor["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                if not db.execute(
                    "SELECT 1 FROM categorias WHERE id=?", (body.categoria_id,)
                ).fetchone():
                    fail(422, "Categoría inexistente")
                values = body.model_dump()
                if id is None:
                    id = db.execute(
                        "INSERT INTO productos("
                        + ",".join(values)
                        + ") VALUES("
                        + ",".join("?" for _ in values)
                        + ")",
                        tuple(values.values()),
                    ).lastrowid
                    status = 201
                else:
                    current = db.execute(
                        "SELECT * FROM productos WHERE id=?", (id,)
                    ).fetchone()
                    if not current:
                        fail(404, "Producto no encontrado")
                    reserved = current["stock"] - free_stock(db)[id]
                    if body.stock < reserved:
                        fail(409, "Stock inferior a las unidades reservadas")
                    db.execute(
                        "UPDATE productos SET "
                        + ",".join(f"{k}=?" for k in values)
                        + " WHERE id=?",
                        (*values.values(), id),
                    )
                    status = 200
                op.save(
                    db,
                    dict(
                        db.execute(
                            "SELECT * FROM productos WHERE id=?", (id,)
                        ).fetchone()
                    ),
                    status,
                )
            return op.response()

    @app.post("/productos", status_code=201)
    async def create(request: Request, body: Producto):
        return await write_product(request, body)

    @app.put("/productos/{id}")
    async def update(id: int, request: Request, body: Producto):
        return await write_product(request, body, id)

    @app.delete("/productos/{id}")
    async def deactivate(id: int, request: Request):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"administrador", "dueno"})
        async with ctx.operation(request, f"desactivar:{id}", user["id"], {}) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                if not db.execute(
                    "UPDATE productos SET activo=0 WHERE id=?", (id,)
                ).rowcount:
                    fail(404, "Producto no encontrado")
                op.save(db, {"id": id, "activo": False})
            return op.response()

    @app.post("/interno/catalogo/consultas")
    async def batch(request: Request, body: Consulta):
        ctx.require_caller(request, "orders", "graphql")
        user = await ctx.actor(request, optional=True)
        with ctx.read() as db:
            prods, combos = catalog(db, user)
        result = []
        for ref in body.items:
            p = (prods if ref.tipo == "producto" else combos).get(ref.id)
            found = p is not None and (ref.tipo == "combo" or p["activo"])
            result.append(
                {
                    "tipo": ref.tipo,
                    "id": ref.id,
                    "encontrado": found,
                    **(
                        {k: p[k] for k in ("nombre", "precio_final", "disponible")}
                        if found
                        else {}
                    ),
                }
            )
        return {"items": result}

    @app.post("/interno/reservas", status_code=201)
    async def reserve(request: Request, body: ReservaIn):
        ctx.require_caller(request, "orders")
        user = await ctx.actor(request, {"cliente"})
        async with ctx.operation(
            request, "reserva", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                with ctx.transaction() as db:
                    return reservation(db, op.cached["id"])
            with ctx.transaction() as db:
                existing = db.execute(
                    "SELECT id FROM reservas WHERE operacion_id=?", (body.operacion_id,)
                ).fetchone()
                if existing:
                    result = reservation(db, existing["id"])
                    op.save(db, result, 201)
                else:
                    prods, combos = catalog(db, user)
                    demand = Counter()
                    lines = []
                    for item in body.items:
                        p = (prods if item.producto_id else combos).get(
                            item.producto_id or item.combo_id
                        )
                        if not p or not p["disponible"]:
                            fail(409, "Ítem no disponible")
                        if item.producto_id:
                            demand[item.producto_id] += item.cantidad
                        else:
                            for component in p["productos"]:
                                demand[component["id"]] += (
                                    item.cantidad * component["cantidad"]
                                )
                        money(p["precio_final"] * item.cantidad)
                        lines.append(
                            (
                                item.producto_id,
                                item.combo_id,
                                p["nombre"],
                                item.cantidad,
                                p["precio_final"],
                            )
                        )
                    subtotal = sum(line[3] * line[4] for line in lines)
                    if subtotal > body.limite_subtotal:
                        fail(422, "Importe fuera de rango")
                    free = free_stock(db)
                    if any(free[id] < qty for id, qty in demand.items()):
                        fail(409, "Stock insuficiente", "INSUFFICIENT_STOCK")
                    id = db.execute(
                        "INSERT INTO reservas(operacion_id,estado,creado_en,vence_en) VALUES(?,'activa',?,?)",
                        (body.operacion_id, now(), later(900)),
                    ).lastrowid
                    db.executemany(
                        "INSERT INTO lineas_reserva(reserva_id,posicion,producto_id,combo_id,nombre,cantidad,precio_unitario) VALUES(?,?,?,?,?,?,?)",
                        [(id, index, *line) for index, line in enumerate(lines, 1)],
                    )
                    db.executemany(
                        "INSERT INTO detalles_reserva(reserva_id,producto_id,cantidad) VALUES(?,?,?)",
                        [(id, pid, qty) for pid, qty in demand.items()],
                    )
                    result = reservation(db, id)
                    op.save(db, result, 201)
            return op.response()

    @app.get("/interno/reservas/{id}")
    async def get_reservation(id: int, request: Request):
        ctx.require_caller(request, "orders")
        with ctx.transaction() as db:
            return reservation(db, id)

    async def move(id, request, body, action):
        ctx.require_caller(request, "orders")
        async with ctx.operation(
            request, f"reserva:{id}:{action}", "orders", body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                r = reservation(db, id)
                if r["pedido_id"] is not None and r["pedido_id"] != body.orden_id:
                    fail(409, "Reserva de otra orden")
                if action == "consumos":
                    if (
                        r["estado"] == "consumida"
                        and r["consumo_operacion"] != body.operacion_id
                    ):
                        fail(409, "Reserva consumida por otra operación")
                    if r["estado"] not in {"activa", "consumida"}:
                        fail(409, "Reserva no consumible")
                    new_state = "consumida"
                    delta = -1 if r["estado"] == "activa" else 0
                elif action == "liberaciones":
                    if r["estado"] in {"consumida", "restituida"}:
                        fail(409, "Reserva ya consumida")
                    new_state = (
                        r["estado"]
                        if r["estado"] in {"liberada", "expirada"}
                        else "liberada"
                    )
                    delta = 0
                else:
                    if r["estado"] not in {"consumida", "restituida"}:
                        fail(409, "No hay consumo que restituir")
                    new_state, delta = (
                        "restituida",
                        1 if r["estado"] == "consumida" else 0,
                    )
                if delta:
                    for detail in db.execute(
                        "SELECT producto_id,cantidad FROM detalles_reserva WHERE reserva_id=?",
                        (id,),
                    ):
                        db.execute(
                            "UPDATE productos SET stock=stock+? WHERE id=?",
                            (delta * detail["cantidad"], detail["producto_id"]),
                        )
                db.execute(
                    "UPDATE reservas SET estado=?,pedido_id=?,consumo_operacion=COALESCE(consumo_operacion,?),version=version+1 WHERE id=?",
                    (
                        new_state,
                        body.orden_id,
                        body.operacion_id if action == "consumos" else None,
                        id,
                    ),
                )
                op.save(db, {"id": id, "estado": new_state})
            return op.response()

    @app.post("/interno/reservas/{id}/consumos")
    async def consume(id: int, request: Request, body: AccionReserva):
        return await move(id, request, body, "consumos")

    @app.post("/interno/reservas/{id}/liberaciones")
    async def release(id: int, request: Request, body: AccionReserva):
        return await move(id, request, body, "liberaciones")

    @app.post("/interno/reservas/{id}/restituciones")
    async def restore(id: int, request: Request, body: AccionReserva):
        return await move(id, request, body, "restituciones")

    return app


app = create_app()
