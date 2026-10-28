import asyncio
import html
import json
import logging
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import Field

from services import seeds
from services.common import (
    MAX_MONEY,
    ORDER_STATES,
    Context,
    application,
    encode,
    fail,
    money,
    now,
    page,
    pagination,
    period,
)
from services.dto import DTO, Asignacion, Checkout, Motivo, Transicion


class PaymentResult(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    pago_id: int = Field(gt=0)
    evento_id: str = Field(min_length=1, max_length=128)
    transaccion_id: str = Field(min_length=1, max_length=128)
    estado: Literal["aprobado", "rechazado", "pendiente"]
    monto: int = Field(ge=0, le=2_147_483_647)
    moneda: Literal["CLP"]
    aprobado_en: str | None = None


class Expiration(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    reserva_id: int = Field(gt=0)


class RefundResult(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    reembolso_id: int = Field(gt=0)
    estado: Literal["pendiente", "completado", "fallido"]
    monto_devuelto: int = Field(ge=0, le=2_147_483_647)
    moneda: Literal["CLP"]


class Approval(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    solicitud_id: int = Field(gt=0)
    decision_id: str = Field(min_length=1, max_length=128)
    administrador_id: int = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=1000)


def seed(ctx):
    with ctx.transaction() as db:
        if not db.execute("SELECT 1 FROM comunas LIMIT 1").fetchone():
            for name, city, region, cost in seeds.COMUNAS:
                id = db.execute(
                    "INSERT INTO comunas(nombre,ciudad,region) VALUES(?,?,?)",
                    (name, city, region),
                ).lastrowid
                db.execute(
                    "INSERT INTO costos_envio(comuna_id,costo) VALUES(?,?)", (id, cost)
                )
        db.execute("INSERT OR IGNORE INTO cajas(id,nombre) VALUES(1,'Web')")


def get_order(db, id, complete=True):
    row = db.execute(
        "SELECT * FROM ordenes WHERE id=?"
        + (" AND checkout_completo=1" if complete else ""),
        (id,),
    ).fetchone()
    if not row:
        fail(404, "Pedido no encontrado")
    return dict(row)


def authorize(db, user, order, report=False):
    role = user["rol"]
    if role == "administrador":
        return
    if role == "cliente" and user["cliente_id"] == order["cliente_id"]:
        return
    if (
        role == "cajero"
        and db.execute(
            "SELECT 1 FROM cajas WHERE id=? AND cajero_id=?",
            (order["caja_id"], user["id"]),
        ).fetchone()
    ):
        return
    if role == "despacho" and order["estado"] in {
        "pagado",
        "preparando",
        "enviado",
        "entregado",
    }:
        return
    fail(404, "Pedido no encontrado")


def event(db, id, kind, previous, state, actor, ref, reason=None):
    db.execute(
        "INSERT OR IGNORE INTO eventos_pedido(orden_id,tipo,estado_anterior,estado,actor,motivo,referencia,fecha) VALUES(?,?,?,?,?,?,?,?)",
        (id, kind, previous, state, str(actor), reason, ref, now()),
    )


def present(db, order, user, history_page=1, history_limit=20):
    id = order["id"]
    allowed_finance = user["rol"] != "despacho"
    sale = db.execute("SELECT id FROM ventas WHERE orden_id=?", (id,)).fetchone()
    receipt = db.execute(
        "SELECT c.id,c.venta_id,c.numero,c.estado_envio FROM comprobantes c JOIN ventas v ON v.id=c.venta_id WHERE v.orden_id=?",
        (id,),
    ).fetchone()
    client = json.loads(order["cliente_snapshot"])
    address = json.loads(order["direccion_snapshot"])
    offset = pagination(history_page, history_limit)
    history = [
        dict(x)
        for x in db.execute(
            "SELECT estado,fecha FROM eventos_pedido WHERE orden_id=? ORDER BY fecha,id LIMIT ? OFFSET ?",
            (id, history_limit, offset),
        )
    ]
    total_events = db.execute(
        "SELECT COUNT(*) FROM eventos_pedido WHERE orden_id=?", (id,)
    ).fetchone()[0]
    lines = []
    for r in db.execute(
        "SELECT * FROM lineas_orden WHERE orden_id=? ORDER BY posicion", (id,)
    ):
        line = {
            "id": r["id"],
            "tipo": "producto" if r["producto_id"] else "combo",
            "referencia_id": r["producto_id"] or r["combo_id"],
            "nombre": r["nombre"],
            "cantidad": r["cantidad"],
        }
        if allowed_finance:
            line.update(
                precio_unitario=r["precio_unitario"],
                subtotal=r["cantidad"] * r["precio_unitario"],
            )
        lines.append(line)
    result = {
        "id": id,
        "cliente_id": order["cliente_id"],
        "caja_id": order["caja_id"],
        "estado": order["estado"],
        "version": order["version"],
        "creado_en": order["created_at"],
        "actualizado_en": order["updated_at"],
        "pagado_en": order["pagado_en"],
        "vence_en": order["vence_en"],
        "moneda": "CLP",
        "cliente": {k: client.get(k) for k in ("nombres", "apellidos", "telefono")},
        "direccion": address,
        "lineas": lines,
        "historial": page(history, total_events, history_page, history_limit),
    }
    if allowed_finance:
        result.update(
            {k: order[k] for k in ("subtotal", "costo_envio", "descuento", "total")}
        )
        result.update(
            venta_id=sale["id"] if sale else None,
            comprobante=dict(receipt) if receipt else None,
        )
    return result


def emit_receipt(ctx, db, sale_id):
    existing = db.execute(
        "SELECT * FROM comprobantes WHERE venta_id=?", (sale_id,)
    ).fetchone()
    if existing:
        return dict(existing)
    sale = db.execute("SELECT * FROM ventas WHERE id=?", (sale_id,)).fetchone()
    order = get_order(db, sale["orden_id"])
    client = json.loads(order["cliente_snapshot"])
    number = f"FE-{sale_id:08d}"
    document = f"<!doctype html><html lang='es'><meta charset='utf-8'><title>{number}</title><h1>Comprobante Fit Express {number}</h1><p>Venta {sale_id} · Pedido {order['id']}</p><ul>"
    for line in db.execute(
        "SELECT * FROM lineas_orden WHERE orden_id=? ORDER BY posicion", (order["id"],)
    ):
        document += f"<li>{line['cantidad']} × {html.escape(line['nombre'])}: ${line['cantidad'] * line['precio_unitario']}</li>"
    document += f"</ul><p>Envío: ${order['costo_envio']}</p><strong>Total CLP ${order['total']}</strong><p>Correo simulado · demostración académica</p></html>"
    message_id = f"comprobante:{sale_id}"
    id = db.execute(
        "INSERT INTO comprobantes(venta_id,numero,contenido,emitido_en,estado_envio,mensaje_id,destinatario,intentos_envio) VALUES(?,?,?,?,'simulado',?,?,1)",
        (sale_id, number, document, now(), message_id, client["email"]),
    ).lastrowid
    ctx.message(
        db, message_id, client["email"], f"Comprobante {number} (simulado)", document
    )
    return dict(db.execute("SELECT * FROM comprobantes WHERE id=?", (id,)).fetchone())


async def stock_move(ctx, order, action, reference):
    return await ctx.call(
        "inventory",
        "POST",
        f"/interno/reservas/{order['reserva_id']}/{action}",
        body={
            "operacion_id": reference,
            "orden_id": order["id"],
            "motivo": "Coordinación autorizada del pedido",
        },
        key=reference,
    )


async def cancel_effects(ctx, order):
    if not order["reserva_id"] or order["causa_cancelacion"] == "reembolso_excepcional":
        return
    reservation = await ctx.call(
        "inventory", "GET", f"/interno/reservas/{order['reserva_id']}"
    )
    if reservation["estado"] == "activa":
        try:
            await stock_move(ctx, order, "liberaciones", f"liberar:{order['id']}")
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            reservation = await ctx.call(
                "inventory", "GET", f"/interno/reservas/{order['reserva_id']}"
            )
    if reservation["estado"] == "consumida":
        await stock_move(ctx, order, "restituciones", f"restituir:{order['id']}")
    payment_id = order["pago_confirmado_id"] or order["pago_en_proceso_id"]
    if payment_id:
        await ctx.call(
            "payments",
            "POST",
            "/interno/reembolsos",
            body={
                "operacion_id": f"cancelacion:{order['id']}",
                "orden_id": order["id"],
                "pago_id": payment_id,
                "causa": "cancelacion_pagada",
            },
            key=f"cancelacion:{order['id']}",
        )


async def payment_result(ctx, id, body):
    with ctx.transaction() as db:
        o = get_order(db, id)
        if body.monto != o["total"] or body.moneda != o["moneda"]:
            fail(409, "Monto/moneda no corresponden al pedido")
        if body.estado != "aprobado":
            return {"id": id, "estado": o["estado"]}
        if o["pago_confirmado_id"] == body.pago_id:
            sale = db.execute(
                "SELECT id FROM ventas WHERE orden_id=?", (id,)
            ).fetchone()
            return {
                "id": id,
                "estado": o["estado"],
                "venta_id": sale["id"] if sale else None,
            }
        if o["pago_confirmado_id"] is not None or (
            o["pago_en_proceso_id"] is not None
            and o["pago_en_proceso_id"] != body.pago_id
        ):
            return {
                "id": id,
                "estado": o["estado"],
                "devolucion_requerida": "cobro_duplicado",
            }
        if o["estado"] in {"cancelado", "expirado"}:
            reason = (
                "cancelacion_pagada" if o["estado"] == "cancelado" else "pago_tardio"
            )
            return {"id": id, "estado": o["estado"], "devolucion_requerida": reason}
        db.execute(
            "UPDATE ordenes SET pago_en_proceso_id=? WHERE id=?", (body.pago_id, id)
        )
    try:
        await stock_move(ctx, o, "consumos", f"consumo-pago:{body.pago_id}")
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        reservation = await ctx.call(
            "inventory", "GET", f"/interno/reservas/{o['reserva_id']}"
        )
        if reservation["estado"] in {"expirada", "liberada", "restituida"}:
            with ctx.transaction() as db:
                current = get_order(db, id)
                if current["estado"] == "pendiente":
                    db.execute(
                        "UPDATE ordenes SET estado='expirado',version=version+1,updated_at=? WHERE id=?",
                        (now(), id),
                    )
                    event(
                        db,
                        id,
                        "vencimiento",
                        "pendiente",
                        "expirado",
                        "orders",
                        f"reserva:{o['reserva_id']}",
                    )
                return {
                    "id": id,
                    "estado": get_order(db, id)["estado"],
                    "devolucion_requerida": "pago_tardio",
                }
        raise
    with ctx.transaction() as db:
        current = get_order(db, id)
        cancelled = current["estado"] in {"cancelado", "expirado"}
        if not cancelled:
            db.execute(
                "UPDATE ordenes SET estado='pagado',pago_confirmado_id=?,pagado_en=COALESCE(pagado_en,?),version=version+1,updated_at=? WHERE id=? AND estado='pendiente'",
                (body.pago_id, now(), now(), id),
            )
            sale_id = db.execute(
                "INSERT OR IGNORE INTO ventas(orden_id,pago_id,caja_id,cajero_id,cajero_identificador,total,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    id,
                    body.pago_id,
                    o["caja_id"],
                    o["cajero_id"],
                    o["cajero_identificador"],
                    o["total"],
                    now(),
                ),
            ).lastrowid
            sale_id = db.execute(
                "SELECT id FROM ventas WHERE orden_id=?", (id,)
            ).fetchone()[0]
            emit_receipt(ctx, db, sale_id)
            event(
                db,
                id,
                "pago",
                current["estado"],
                "pagado",
                "payments",
                f"pago:{body.pago_id}",
            )
            return {"id": id, "estado": "pagado", "venta_id": sale_id}
    # Cancelar ganó mientras el consumo viajaba: compensación única y devolución.
    await cancel_effects(ctx, current)
    return {
        "id": id,
        "estado": current["estado"],
        "devolucion_requerida": "cancelacion_pagada",
    }


async def expire(ctx, id):
    with ctx.read() as db:
        o = get_order(db, id)
    if o["estado"] != "pendiente" or o["vence_en"] > now():
        return {"id": id, "estado": o["estado"]}
    reservation = await ctx.call(
        "inventory", "GET", f"/interno/reservas/{o['reserva_id']}"
    )
    if reservation["estado"] == "consumida":
        # El proveedor puede repetir el aviso de pago; no liberar unidades consumidas.
        return {"id": id, "estado": "pendiente", "conciliacion": True}
    if reservation["estado"] == "activa":
        await stock_move(ctx, o, "liberaciones", f"vencimiento:{id}")
    with ctx.transaction() as db:
        if db.execute(
            "UPDATE ordenes SET estado='expirado',version=version+1,updated_at=? WHERE id=? AND estado='pendiente'",
            (now(), id),
        ).rowcount:
            event(
                db,
                id,
                "vencimiento",
                "pendiente",
                "expirado",
                "orders",
                f"reserva:{o['reserva_id']}",
            )
        return {"id": id, "estado": get_order(db, id)["estado"]}


async def worker(ctx):
    while True:
        try:
            with ctx.read() as db:
                due = [
                    r[0]
                    for r in db.execute(
                        "SELECT id FROM ordenes WHERE checkout_completo=1 AND estado='pendiente' AND vence_en<=? LIMIT 50",
                        (now(),),
                    )
                ]
            for id in due:
                try:
                    await expire(ctx, id)
                except HTTPException:
                    pass
        except Exception as exc:  # noqa: BLE001 -- frontera del worker; continuar sin registrar datos privados
            # No escribir cuerpos, direcciones, tokens o errores del proveedor en logs.
            logging.getLogger("fitexpress").warning(
                "orders.worker: %s", type(exc).__name__
            )
        await asyncio.sleep(1)


def create_app(ctx=None):
    ctx = ctx or Context("orders")
    app = application(ctx, startup=seed, worker=worker)

    @app.get("/comunas")
    async def communes(request: Request):
        ctx.require_caller(request, "gateway", "clients")
        with ctx.read() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT c.id,c.nombre,c.ciudad,c.region,e.costo AS costo_envio FROM comunas c JOIN costos_envio e ON e.comuna_id=c.id WHERE c.habilitada=1 ORDER BY c.nombre,c.id"
                )
            ]

    @app.post("/ordenes", status_code=201)
    async def checkout(request: Request, body: Checkout):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente"})
        async with ctx.operation(
            request, "checkout", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            if "orden_id" not in op.data:
                client = await ctx.call(
                    "clients", "GET", f"/interno/clientes/{user['cliente_id']}", request
                )
                with ctx.read() as db:
                    box = dict(db.execute("SELECT * FROM cajas WHERE id=1").fetchone())
                    row = db.execute(
                        "SELECT c.*,e.costo FROM comunas c JOIN costos_envio e ON e.comuna_id=c.id WHERE c.id=? AND c.habilitada=1",
                        (body.direccion.comuna_id,),
                    ).fetchone()
                if not row:
                    fail(422, "Sin despacho a esa comuna")
                if not box["cajero_id"]:
                    fail(409, "Caja Web sin cajero habilitado")
                cashier = await ctx.call(
                    "clients", "GET", f"/interno/usuarios/{box['cajero_id']}", request
                )
                if not cashier["activo"] or cashier["rol"] != "cajero":
                    fail(409, "Caja Web sin cajero habilitado")
                address = {
                    **body.direccion.model_dump(),
                    "comuna": row["nombre"],
                    "ciudad": row["ciudad"],
                    "region": row["region"],
                }
                snapshot = {
                    k: client[k] for k in ("nombres", "apellidos", "email", "telefono")
                }
                with ctx.transaction() as db:
                    id = db.execute(
                        "INSERT INTO ordenes(operacion_checkout,cliente_id,cliente_snapshot,direccion_snapshot,comuna_id,caja_id,cajero_id,cajero_identificador,costo_envio,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            op.id,
                            user["cliente_id"],
                            encode(snapshot),
                            encode(address),
                            row["id"],
                            1,
                            cashier["id"],
                            cashier["identificador"],
                            row["costo"],
                            now(),
                            now(),
                        ),
                    ).lastrowid
                    op.save(db, orden_id=id)
            id = op.data["orden_id"]
            with ctx.read() as db:
                shipping = get_order(db, id, False)["costo_envio"]
            reservation = await ctx.call(
                "inventory",
                "POST",
                "/interno/reservas",
                request,
                body={
                    "operacion_id": op.id,
                    "items": [i.model_dump() for i in body.items],
                    "limite_subtotal": MAX_MONEY - shipping,
                },
                key=op.id,
            )
            subtotal = sum(x["subtotal"] for x in reservation["lineas"])
            with ctx.transaction() as db:
                o = get_order(db, id, False)
                total = money(subtotal + o["costo_envio"])
                state = "pendiente" if reservation["estado"] == "activa" else "expirado"
                db.execute(
                    "UPDATE ordenes SET reserva_id=?,vence_en=?,subtotal=?,total=?,estado=?,checkout_completo=1,updated_at=? WHERE id=?",
                    (
                        reservation["id"],
                        reservation["vence_en"],
                        subtotal,
                        total,
                        state,
                        now(),
                        id,
                    ),
                )
                for index, line in enumerate(reservation["lineas"], 1):
                    db.execute(
                        "INSERT OR IGNORE INTO lineas_orden(orden_id,posicion,producto_id,combo_id,nombre,cantidad,precio_unitario) VALUES(?,?,?,?,?,?,?)",
                        (
                            id,
                            index,
                            line["producto_id"],
                            line["combo_id"],
                            line["nombre"],
                            line["cantidad"],
                            line["precio_unitario"],
                        ),
                    )
                event(db, id, "creacion", None, state, user["id"], op.id)
                op.save(
                    db,
                    {
                        "id": id,
                        "subtotal": subtotal,
                        "costo_envio": o["costo_envio"],
                        "total": total,
                        "estado": state,
                        "reserva_id": reservation["id"],
                        "vence_en": reservation["vence_en"],
                    },
                    201,
                )
            return op.response()

    @app.get("/ordenes")
    async def listing(
        request: Request,
        pagina: int = 1,
        limite: int = 20,
        estado: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ):
        ctx.require_caller(request, "graphql")
        u = await ctx.actor(request, {"cliente", "administrador", "cajero", "despacho"})
        offset = pagination(pagina, limite)
        where, args = ["checkout_completo=1"], []
        if estado:
            if estado not in ORDER_STATES:
                fail(422, "Estado inválido")
            where.append("estado=?")
            args.append(estado)
        if desde or hasta:
            start, end = period(desde or "1970-01-01", hasta or "9998-12-31")
            where.extend(["created_at>=?", "created_at<?"])
            args.extend([start, end])
        if u["rol"] == "cliente":
            where.append("cliente_id=?")
            args.append(u["cliente_id"])
        if u["rol"] == "cajero":
            where.append("caja_id IN(SELECT id FROM cajas WHERE cajero_id=?)")
            args.append(u["id"])
        if u["rol"] == "despacho":
            where.append("estado IN('pagado','preparando','enviado','entregado')")
        clause = " AND ".join(where)
        ordering = (
            "pagado_en,id" if u["rol"] == "despacho" else "created_at DESC,id DESC"
        )
        with ctx.read() as db:
            total = db.execute(
                f"SELECT COUNT(*) FROM ordenes WHERE {clause}", args
            ).fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM ordenes WHERE {clause} ORDER BY {ordering} LIMIT ? OFFSET ?",
                (*args, limite, offset),
            ).fetchall()
            values = []
            for row in rows:
                value = {
                    "id": row["id"],
                    "estado": row["estado"],
                    "creado_en": row["created_at"],
                    "pagado_en": row["pagado_en"],
                    "moneda": "CLP",
                }
                if u["rol"] != "despacho":
                    sale = db.execute(
                        "SELECT id FROM ventas WHERE orden_id=?", (row["id"],)
                    ).fetchone()
                    value.update(total=row["total"], venta_id=sale[0] if sale else None)
                values.append(value)
        return page(values, total, pagina, limite)

    @app.get("/ordenes/{id}")
    async def detail(
        id: int, request: Request, historial_pagina: int = 1, historial_limite: int = 20
    ):
        ctx.require_caller(request, "graphql")
        user = await ctx.actor(request)
        with ctx.read() as db:
            o = get_order(db, id)
            authorize(db, user, o)
            return present(db, o, user, historial_pagina, historial_limite)

    @app.post("/ordenes/{id}/cancelaciones")
    async def cancel(id: int, request: Request, body: Motivo):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente", "administrador"})
        async with ctx.operation(
            request, f"cancelar:{id}", user["id"], body.model_dump()
        ) as op:
            with ctx.read() as db:
                authorize(db, user, get_order(db, id))
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                o = get_order(db, id)
                if o["estado"] not in {"pendiente", "pagado"}:
                    if o["estado"] != "cancelado" or "orden_id" not in op.data:
                        fail(409, "Cancelación normal no permitida")
                else:
                    if body.version and body.version != o["version"]:
                        fail(409, "Versión desactualizada")
                    db.execute(
                        "UPDATE ordenes SET estado='cancelado',causa_cancelacion='cancelacion_normal',motivo_cancelacion=?,cancelado_por=?,cancelado_en=?,version=version+1,updated_at=? WHERE id=?",
                        (body.motivo, str(user["id"]), now(), now(), id),
                    )
                    event(
                        db,
                        id,
                        "cancelacion",
                        o["estado"],
                        "cancelado",
                        user["id"],
                        op.id,
                        body.motivo,
                    )
                    op.save(db, orden_id=id)
                o = get_order(db, id)
            try:
                await cancel_effects(ctx, o)
            except HTTPException as exc:
                if exc.status_code < 500:
                    raise
                return JSONResponse(
                    {"operacion_id": op.id, "estado": "procesando"},
                    status_code=202,
                    headers={"Retry-After": "2"},
                )
            with ctx.transaction() as db:
                op.save(db, {"id": id, "estado": "cancelado"})
            return op.response()

    async def transition(id, request, body, source, destination):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"despacho"})
        async with ctx.operation(
            request, f"{destination}:{id}", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                o = get_order(db, id)
                if o["estado"] != source or (
                    body.version and o["version"] != body.version
                ):
                    fail(409, "Transición o versión inválida")
                db.execute(
                    "UPDATE ordenes SET estado=?,version=version+1,updated_at=? WHERE id=?",
                    (destination, now(), id),
                )
                event(db, id, "transicion", source, destination, user["id"], op.id)
                op.save(
                    db, {"id": id, "estado": destination, "version": o["version"] + 1}
                )
            return op.response()

    @app.post("/ordenes/{id}/preparacion")
    async def prepare(id: int, request: Request, body: Transicion):
        return await transition(id, request, body, "pagado", "preparando")

    @app.post("/ordenes/{id}/envios")
    async def dispatch(id: int, request: Request, body: Transicion):
        return await transition(id, request, body, "preparando", "enviado")

    @app.post("/ordenes/{id}/entregas")
    async def deliver(id: int, request: Request, body: Transicion):
        return await transition(id, request, body, "enviado", "entregado")

    @app.get("/ordenes/{id}/orden-despacho", response_class=HTMLResponse)
    async def kitchen(id: int, request: Request):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"despacho"})
        with ctx.read() as db:
            o = get_order(db, id)
            authorize(db, user, o)
            data = present(db, o, user)
        lines = "".join(
            f"<li>{x['cantidad']} × {html.escape(x['nombre'])}</li>"
            for x in data["lineas"]
        )
        addr = data["direccion"]
        return HTMLResponse(
            f"<!doctype html><html lang='es'><meta charset='utf-8'><h1>Despacho #{id}</h1><p>{html.escape(data['cliente']['nombres'])}</p><p>{html.escape(addr['calle'])} {html.escape(addr['numero'])}, {html.escape(addr['comuna'])}</p><ul>{lines}</ul></html>"
        )

    @app.get("/cajas")
    async def boxes(request: Request):
        ctx.require_caller(request, "gateway", "payments")
        user = await ctx.actor(request, {"administrador", "cajero"})
        with ctx.read() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM cajas"
                    + (" WHERE cajero_id=?" if user["rol"] == "cajero" else ""),
                    (user["id"],) if user["rol"] == "cajero" else (),
                )
            ]

    @app.patch("/cajas/{id}")
    async def assign(id: int, request: Request, body: Asignacion):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"administrador"})
        cashier = await ctx.call(
            "clients", "GET", f"/interno/usuarios/{body.cajero_id}", request
        )
        if cashier["rol"] != "cajero" or not cashier["activo"]:
            fail(409, "Cajero no habilitado")
        async with ctx.operation(
            request, f"caja:{id}", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                if not db.execute(
                    "UPDATE cajas SET cajero_id=? WHERE id=?", (body.cajero_id, id)
                ).rowcount:
                    fail(404, "Caja no encontrada")
                op.save(db, {"id": id, "nombre": "Web", "cajero_id": body.cajero_id})
            return op.response()

    @app.get("/reportes/ventas")
    async def report(
        request: Request, desde: str, hasta: str, pagina: int = 1, limite: int = 20
    ):
        ctx.require_caller(request, "graphql")
        await ctx.actor(request, {"administrador", "dueno"})
        offset = pagination(pagina, limite)
        start, end = period(desde, hasta)
        with ctx.read() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM ventas WHERE created_at>=? AND created_at<?",
                (start, end),
            ).fetchone()[0]
            rows = db.execute(
                "SELECT v.id,v.orden_id AS pedido_id,v.created_at AS fecha,o.estado AS estado_pedido,v.total FROM ventas v JOIN ordenes o ON o.id=v.orden_id WHERE v.created_at>=? AND v.created_at<? ORDER BY v.created_at DESC,v.id DESC LIMIT ? OFFSET ?",
                (start, end, limite, offset),
            ).fetchall()
        return {
            "desde": desde,
            "hasta": hasta,
            "zona_horaria": "America/Santiago",
            "moneda": "CLP",
            "cantidad_ventas": total,
            "ventas": page([dict(r) for r in rows], total, pagina, limite),
        }

    async def receipt_access(request, sale_id, roles):
        user = await ctx.actor(request, roles)
        with ctx.read() as db:
            sale = db.execute("SELECT * FROM ventas WHERE id=?", (sale_id,)).fetchone()
            if not sale:
                fail(404, "Venta no encontrada")
            authorize(db, user, get_order(db, sale["orden_id"]))
        return user

    @app.get("/ventas/{id}/comprobante", response_class=HTMLResponse)
    async def download(id: int, request: Request):
        ctx.require_caller(request, "gateway")
        await receipt_access(request, id, {"cliente", "cajero", "administrador"})
        with ctx.read() as db:
            receipt = db.execute(
                "SELECT contenido FROM comprobantes WHERE venta_id=?", (id,)
            ).fetchone()
        if not receipt:
            fail(404, "Comprobante no emitido")
        return HTMLResponse(receipt[0])

    async def resend(id, request, send):
        ctx.require_caller(request, "gateway")
        user = await receipt_access(request, id, {"cajero"})
        async with ctx.operation(
            request, f"comprobante:{id}:{send}", user["id"], {}
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                receipt = emit_receipt(ctx, db, id)
                if send:
                    db.execute(
                        "UPDATE comprobantes SET estado_envio='simulado',intentos_envio=intentos_envio+1,ultimo_error=NULL WHERE id=?",
                        (receipt["id"],),
                    )
                op.save(
                    db,
                    {
                        "id": receipt["id"],
                        "venta_id": id,
                        "numero": receipt["numero"],
                        "estado_envio": "simulado",
                    },
                )
            return op.response()

    @app.post("/ventas/{id}/comprobantes")
    async def emit(id: int, request: Request):
        return await resend(id, request, False)

    @app.post("/ventas/{id}/comprobante/envios")
    async def send(id: int, request: Request):
        return await resend(id, request, True)

    @app.get("/interno/ordenes/{id}/cobro")
    async def charge_data(id: int, request: Request):
        ctx.require_caller(request, "payments")
        with ctx.read() as db:
            o = get_order(db, id)
            current_cashier = db.execute(
                "SELECT cajero_id FROM cajas WHERE id=?", (o["caja_id"],)
            ).fetchone()[0]
        enabled = False
        if current_cashier:
            cashier = await ctx.call(
                "clients", "GET", f"/interno/usuarios/{current_cashier}"
            )
            enabled = cashier["rol"] == "cajero" and bool(cashier["activo"])
        return {
            **{
                k: o[k]
                for k in (
                    "id",
                    "cliente_id",
                    "caja_id",
                    "cajero_id",
                    "estado",
                    "total",
                    "moneda",
                    "reserva_id",
                    "vence_en",
                    "pago_confirmado_id",
                    "causa_cancelacion",
                )
            },
            "caja_habilitada": enabled,
            "cajero_actual_id": current_cashier,
        }

    @app.post("/interno/ordenes/{id}/resultados-pago")
    async def paid(id: int, request: Request, body: PaymentResult):
        ctx.require_caller(request, "payments")
        return await payment_result(ctx, id, body)

    @app.post("/interno/ordenes/{id}/vencimientos")
    async def expiration(id: int, request: Request, body: Expiration):
        ctx.require_caller(request, "orders")
        with ctx.read() as db:
            if get_order(db, id)["reserva_id"] != body.reserva_id:
                fail(409, "Reserva no corresponde")
        return await expire(ctx, id)

    @app.post("/interno/ordenes/{id}/resultados-reembolso")
    async def refund_result(id: int, request: Request, body: RefundResult):
        ctx.require_caller(request, "payments")
        with ctx.transaction() as db:
            o = get_order(db, id)
            event(
                db,
                id,
                "reembolso",
                o["estado"],
                o["estado"],
                "payments",
                f"{body.reembolso_id}:{body.estado}",
            )
        return {"id": id, "estado": o["estado"], "reembolso_id": body.reembolso_id}

    @app.post("/interno/ordenes/{id}/autorizaciones-reembolso")
    async def approval(id: int, request: Request, body: Approval):
        ctx.require_caller(request, "payments")
        async with ctx.operation(
            request, f"excepcion:{id}", "payments", body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                o = get_order(db, id)
                if o["estado"] not in {"preparando", "enviado", "entregado"}:
                    fail(409, "Pedido no admite excepción")
                state = "cancelado" if o["estado"] == "preparando" else o["estado"]
                if state == "cancelado":
                    db.execute(
                        "UPDATE ordenes SET estado='cancelado',causa_cancelacion='reembolso_excepcional',motivo_cancelacion=?,cancelado_por=?,cancelado_en=?,version=version+1,updated_at=? WHERE id=?",
                        (body.motivo, str(body.administrador_id), now(), now(), id),
                    )
                event(
                    db,
                    id,
                    "excepcion",
                    o["estado"],
                    state,
                    body.administrador_id,
                    body.decision_id,
                    body.motivo,
                )
                op.save(
                    db,
                    {
                        "id": id,
                        "estado": state,
                        "causa_cancelacion": "reembolso_excepcional",
                        "stock_restituido": False,
                    },
                )
            return op.response()

    return app


app = create_app()
