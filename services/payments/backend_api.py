import asyncio
import hashlib
import hmac
import json
import time
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from services.common import (
    Context,
    application,
    encode,
    fail,
    now,
    page,
    pagination,
    period,
)
from services.dto import DTO, Decision, InicioPago, Solicitud


class Notice(DTO):
    evento_id: str = Field(min_length=1, max_length=128)
    tipo: Literal["pago"]
    transaccion_id: str = Field(min_length=1, max_length=128)
    estado: Literal["pendiente", "aprobado", "rechazado"]
    monto: int = Field(ge=0, le=2_147_483_647)
    moneda: Literal["CLP"]


class TechnicalRefund(DTO):
    operacion_id: str = Field(min_length=1, max_length=128)
    orden_id: int = Field(gt=0)
    pago_id: int = Field(gt=0)
    causa: Literal["cancelacion_pagada", "pago_tardio", "cobro_duplicado"]


class PaymentBatch(DTO):
    pedido_ids: list[int] = Field(max_length=50)


class Empty(DTO):
    pass


def payment_public(p):
    return {
        "id": p["id"],
        "pedido_id": p["pedido_id"],
        "estado": p["estado"],
        "monto": p["monto"],
        "moneda": p["moneda"],
        "creado_en": p["created_at"],
        "actualizado_en": p["updated_at"],
    }


def refund_public(db, r, admin=False):
    p = db.execute("SELECT pedido_id FROM pagos WHERE id=?", (r["pago_id"],)).fetchone()
    attempt = db.execute(
        "SELECT * FROM intentos_reembolso WHERE reembolso_id=? ORDER BY numero DESC LIMIT 1",
        (r["id"],),
    ).fetchone()
    return {
        "id": r["id"],
        "pedido_id": p[0],
        "pago_id": r["pago_id"],
        "estado": r["estado"],
        "monto_solicitado": r["monto_solicitado"],
        "monto_devuelto": r["monto_devuelto"],
        "moneda": r["moneda"],
        "causa": r["causa"],
        "solicitud_id": r["solicitud_id"],
        "reintentable": bool(
            admin
            and r["estado"] != "completado"
            and (not attempt or attempt["estado"] in {"fallido", "pendiente"})
        ),
    }


async def notify_refund(ctx, id):
    with ctx.read() as db:
        r = db.execute(
            "SELECT r.*,p.pedido_id FROM reembolsos r JOIN pagos p ON p.id=r.pago_id WHERE r.id=?",
            (id,),
        ).fetchone()
    await ctx.call(
        "orders",
        "POST",
        f"/interno/ordenes/{r['pedido_id']}/resultados-reembolso",
        body={
            "operacion_id": f"reembolso:{id}:{r['estado']}",
            "reembolso_id": id,
            "estado": r["estado"],
            "monto_devuelto": r["monto_devuelto"],
            "moneda": r["moneda"],
        },
        key=f"reembolso:{id}:{r['estado']}",
    )


async def execute_refund(ctx, id, actor=None, retry=False):
    lock = ctx.locks.setdefault(f"refund:{id}", asyncio.Lock())
    async with lock:
        with ctx.read() as db:
            existing = db.execute(
                "SELECT estado FROM reembolsos WHERE id=?", (id,)
            ).fetchone()
        if existing and existing["estado"] == "completado":
            await notify_refund(ctx, id)
            with ctx.read() as db:
                return refund_public(
                    db,
                    db.execute("SELECT * FROM reembolsos WHERE id=?", (id,)).fetchone(),
                    actor is not None,
                )
        with ctx.transaction() as db:
            r = db.execute(
                "SELECT r.*,p.transaccion_id FROM reembolsos r JOIN pagos p ON p.id=r.pago_id WHERE r.id=?",
                (id,),
            ).fetchone()
            if not r:
                fail(404, "Reembolso no encontrado")
            attempt = db.execute(
                "SELECT * FROM intentos_reembolso WHERE reembolso_id=? ORDER BY numero DESC LIMIT 1",
                (id,),
            ).fetchone()
            if attempt and not retry:
                return refund_public(db, r, actor is not None)
            if attempt and attempt["estado"] == "fallido":
                attempt = None
            if not attempt:
                number = db.execute(
                    "SELECT COALESCE(MAX(numero),0)+1 FROM intentos_reembolso WHERE reembolso_id=?",
                    (id,),
                ).fetchone()[0]
                key = f"devolucion:{id}:intento:{number}"
                aid = db.execute(
                    "INSERT INTO intentos_reembolso(reembolso_id,numero,clave,estado,iniciado_por,created_at) VALUES(?,?,?,'pendiente',?,?)",
                    (id, number, key, actor, now()),
                ).lastrowid
                db.execute(
                    "UPDATE reembolsos SET estado='pendiente' WHERE id=?",
                    (id,),
                )
                attempt = db.execute(
                    "SELECT * FROM intentos_reembolso WHERE id=?", (aid,)
                ).fetchone()
            r, attempt = dict(r), dict(attempt)
        try:
            result = await ctx.call(
                "simulator",
                "POST",
                f"/transacciones/{r['transaccion_id']}/reembolsos",
                body={"monto": r["monto_solicitado"], "moneda": r["moneda"]},
                key=attempt["clave"],
            )
            # Verificación independiente, incluso si la creación respondió satisfactoriamente.
            verified = await ctx.call("simulator", "GET", f"/reembolsos/{result['id']}")
            if (
                verified["monto"] != r["monto_solicitado"]
                or verified["moneda"] != r["moneda"]
                or verified["transaccion_id"] != r["transaccion_id"]
                or verified["estado"] not in {"completado", "fallido"}
            ):
                fail(502, "Resultado financiero inconsistente")
            with ctx.transaction() as db:
                db.execute(
                    "UPDATE intentos_reembolso SET referencia=?,estado=?,verificado_en=?,error=NULL WHERE id=?",
                    (verified["id"], verified["estado"], now(), attempt["id"]),
                )
                db.execute(
                    "UPDATE reembolsos SET estado=?,monto_devuelto=?,completado_en=? WHERE id=?",
                    (
                        verified["estado"],
                        r["monto_solicitado"]
                        if verified["estado"] == "completado"
                        else 0,
                        verified.get("completado_en"),
                        id,
                    ),
                )
        except HTTPException as exc:
            with ctx.transaction() as db:
                db.execute(
                    "UPDATE intentos_reembolso SET error=? WHERE id=?",
                    (f"DEPENDENCY_HTTP_{exc.status_code}", attempt["id"]),
                )
            # Desconocido permanece pendiente. No programar nuevos intentos automáticos.
        await notify_refund(ctx, id)
        with ctx.read() as db:
            return refund_public(
                db,
                db.execute("SELECT * FROM reembolsos WHERE id=?", (id,)).fetchone(),
                actor is not None,
            )


async def ensure_refund(ctx, payment_id, cause, authorization, solicitation=None):
    with ctx.transaction() as db:
        p = db.execute("SELECT * FROM pagos WHERE id=?", (payment_id,)).fetchone()
        if not p or p["estado"] != "aprobado":
            fail(409, "Cobro no aprobado")
        r = db.execute(
            "SELECT * FROM reembolsos WHERE pago_id=?", (payment_id,)
        ).fetchone()
        if r:
            rid = r["id"]
        else:
            rid = db.execute(
                "INSERT INTO reembolsos(pago_id,solicitud_id,causa,autorizacion,monto_solicitado,created_at) VALUES(?,?,?,?,?,?)",
                (payment_id, solicitation, cause, authorization, p["monto"], now()),
            ).lastrowid
    return await execute_refund(ctx, rid)


async def approved_solicitation(ctx, id):
    with ctx.read() as db:
        s = dict(
            db.execute(
                "SELECT * FROM solicitudes_reembolso WHERE id=?", (id,)
            ).fetchone()
        )
    await ctx.call(
        "orders",
        "POST",
        f"/interno/ordenes/{s['pedido_id']}/autorizaciones-reembolso",
        body={
            "operacion_id": s["decision_id"],
            "solicitud_id": id,
            "decision_id": s["decision_id"],
            "administrador_id": s["administrador_id"],
            "motivo": s["motivo_decision"],
        },
        key=s["decision_id"],
    )
    return await ensure_refund(ctx, s["pago_id"], "excepcional", s["decision_id"], id)


async def process_event(ctx, id):
    lock = ctx.locks.setdefault(f"event:{id}", asyncio.Lock())
    async with lock:
        with ctx.read() as db:
            event = db.execute(
                "SELECT * FROM eventos_proveedor WHERE id=?", (id,)
            ).fetchone()
            if not event or event["procesado_en"]:
                return
        verified = await ctx.call(
            "simulator", "GET", f"/transacciones/{event['transaccion_id']}"
        )
        with ctx.transaction() as db:
            p = db.execute(
                "SELECT * FROM pagos WHERE transaccion_id=?",
                (event["transaccion_id"],),
            ).fetchone()
            if not p:
                fail(503, "Transacción aún en conciliación")
            if (
                verified["monto"] != p["monto"]
                or verified["moneda"] != p["moneda"]
                or verified["estado"] not in {"pendiente", "aprobado", "rechazado"}
            ):
                fail(409, "Resultado del proveedor inconsistente")
            payload = json.loads(event["datos"])
            if payload["monto"] != p["monto"] or payload["moneda"] != p["moneda"]:
                fail(409, "Aviso con importe inconsistente")
            # Una confirmación definitiva no retrocede por un aviso antiguo.
            state = "aprobado" if p["estado"] == "aprobado" else verified["estado"]
            db.execute(
                "UPDATE pagos SET estado=?,aprobado_en=COALESCE(aprobado_en,?),verificado_en=?,updated_at=? WHERE id=?",
                (state, verified.get("aprobado_en"), now(), now(), p["id"]),
            )
            p = dict(
                db.execute("SELECT * FROM pagos WHERE id=?", (p["id"],)).fetchone()
            )
        result = await ctx.call(
            "orders",
            "POST",
            f"/interno/ordenes/{p['pedido_id']}/resultados-pago",
            body={
                "operacion_id": f"pago:{p['id']}",
                "pago_id": p["id"],
                "evento_id": event["evento_id"],
                "transaccion_id": p["transaccion_id"],
                "estado": p["estado"],
                "monto": p["monto"],
                "moneda": p["moneda"],
                "aprobado_en": p["aprobado_en"],
            },
            key=f"pago:{p['id']}",
        )
        if result.get("devolucion_requerida"):
            await ensure_refund(
                ctx,
                p["id"],
                result["devolucion_requerida"],
                f"resultado-orders:{p['id']}",
            )
        elif result.get("venta_id"):
            with ctx.transaction() as db:
                db.execute("UPDATE pagos SET aceptado=1 WHERE id=?", (p["id"],))
        with ctx.transaction() as db:
            db.execute(
                "UPDATE eventos_proveedor SET procesado_en=? WHERE id=?",
                (now(), id),
            )


def create_app(ctx=None):
    ctx = ctx or Context("payments")
    app = application(ctx)

    async def boxes_for(user, request):
        if user["rol"] == "cajero":
            return {x["id"] for x in await ctx.call("orders", "GET", "/cajas", request)}
        return set()

    def permitted(user, p, boxes):
        if (
            user["rol"] == "administrador"
            or (user["rol"] == "cliente" and user["cliente_id"] == p["cliente_id"])
            or (user["rol"] == "cajero" and p["caja_id"] in boxes)
        ):
            return
        fail(404, "Pago no encontrado")

    @app.post("/pagos", status_code=201)
    async def start(request: Request, body: InicioPago):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente", "cajero"})
        boxes = await boxes_for(user, request)
        async with ctx.operation(
            request, f"pago:{body.orden_id}", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            o = await ctx.call(
                "orders", "GET", f"/interno/ordenes/{body.orden_id}/cobro", request
            )
            permitted(user, o, boxes)
            if (
                o["estado"] != "pendiente"
                or o["vence_en"] <= now()
                or not o["caja_habilitada"]
            ):
                fail(409, "Pedido no admite iniciar pago")
            # Revalidar la caja actual sin cambiar su atribución histórica.
            with ctx.transaction() as db:
                p = db.execute(
                    "SELECT * FROM pagos WHERE pedido_id=? AND estado='pendiente'",
                    (o["id"],),
                ).fetchone()
                if not p:
                    id = db.execute(
                        "INSERT INTO pagos(pedido_id,cliente_id,caja_id,cajero_id,monto,vence_en,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            o["id"],
                            o["cliente_id"],
                            o["caja_id"],
                            o["cajero_id"],
                            o["total"],
                            o["vence_en"],
                            now(),
                            now(),
                        ),
                    ).lastrowid
                    p = db.execute("SELECT * FROM pagos WHERE id=?", (id,)).fetchone()
                p = dict(p)
                op.save(db, pago_id=p["id"])
            result = await ctx.call(
                "simulator",
                "POST",
                "/transacciones",
                body={
                    "referencia": f"pago:{p['id']}",
                    "monto": p["monto"],
                    "moneda": p["moneda"],
                },
                key=f"pago:{p['id']}",
            )
            if result["monto"] != p["monto"] or result["moneda"] != p["moneda"]:
                fail(502, "Respuesta del proveedor inconsistente")
            with ctx.transaction() as db:
                db.execute(
                    "UPDATE pagos SET transaccion_id=?,checkout_url=?,updated_at=? WHERE id=?",
                    (result["transaccion_id"], result["checkout_url"], now(), p["id"]),
                )
                op.save(
                    db,
                    {**payment_public(p), "checkout_url": result["checkout_url"]},
                    201,
                )
            return op.response()

    @app.get("/pagos/{id}")
    async def payment(id: int, request: Request):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente", "cajero", "administrador"})
        boxes = await boxes_for(user, request)
        with ctx.read() as db:
            p = db.execute("SELECT * FROM pagos WHERE id=?", (id,)).fetchone()
            if not p:
                fail(404, "Pago no encontrado")
            permitted(user, p, boxes)
            return payment_public(p)

    @app.post("/webhooks/pagos/{proveedor}")
    async def webhook(proveedor: str, request: Request, body: Notice):
        ctx.require_caller(request, "gateway", "simulator")
        if proveedor != "simulado":
            fail(404, "Proveedor no configurado")
        stamp = request.headers.get("x-proveedor-timestamp", "")
        try:
            valid_time = abs(time.time() - int(stamp)) <= 300
        except ValueError:
            valid_time = False
        signature = hmac.new(
            ctx.keys["provider_hmac"].encode(),
            stamp.encode() + b"." + await request.body(),
            hashlib.sha256,
        ).hexdigest()
        if not valid_time or not hmac.compare_digest(
            signature, request.headers.get("x-proveedor-firma", "")
        ):
            fail(403, "Firma del proveedor inválida")
        with ctx.transaction() as db:
            old = db.execute(
                "SELECT id,datos FROM eventos_proveedor WHERE evento_id=?",
                (body.evento_id,),
            ).fetchone()
            if old and old["datos"] != encode(body.model_dump()):
                fail(409, "Evento repetido con otro contenido")
            event_id = (
                old["id"]
                if old
                else db.execute(
                    "INSERT INTO eventos_proveedor(evento_id,tipo,transaccion_id,datos,recibido_en) VALUES(?,?,?,?,?)",
                    (
                        body.evento_id,
                        body.tipo,
                        body.transaccion_id,
                        encode(body.model_dump()),
                        now(),
                    ),
                ).lastrowid
            )
        # Flujo directo: verificar proveedor y actualizar pedido antes de responder.
        # Si falla una dependencia, el mismo aviso puede enviarse de nuevo.
        await process_event(ctx, event_id)
        return {"recibido": True, "duplicado": old is not None}

    @app.post("/solicitudes-reembolso", status_code=201)
    async def request_refund(request: Request, body: Solicitud):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente"})
        o = await ctx.call(
            "orders", "GET", f"/interno/ordenes/{body.pedido_id}/cobro", request
        )
        if o["cliente_id"] != user["cliente_id"]:
            fail(404, "Pedido no encontrado")
        async with ctx.operation(
            request, "solicitud-reembolso", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            if (
                o["estado"] not in {"preparando", "enviado", "entregado"}
                or not o["pago_confirmado_id"]
            ):
                fail(409, "Pedido no admite solicitud excepcional")
            with ctx.transaction() as db:
                pay = db.execute(
                    "SELECT * FROM pagos WHERE id=? AND estado='aprobado'",
                    (o["pago_confirmado_id"],),
                ).fetchone()
                if (
                    not pay
                    or db.execute(
                        "SELECT 1 FROM reembolsos WHERE pago_id=?", (pay["id"],)
                    ).fetchone()
                ):
                    fail(409, "Existe un proceso de devolución")
                prior = db.execute(
                    "SELECT motivo FROM solicitudes_reembolso WHERE pedido_id=? ORDER BY id DESC LIMIT 1",
                    (body.pedido_id,),
                ).fetchone()
                if prior and prior["motivo"].strip() == body.motivo:
                    fail(409, "Aportar nuevos antecedentes tras el rechazo")
                id = db.execute(
                    "INSERT INTO solicitudes_reembolso(pedido_id,pago_id,cliente_id,motivo,created_at) VALUES(?,?,?,?,?)",
                    (body.pedido_id, pay["id"], user["cliente_id"], body.motivo, now()),
                ).lastrowid
                op.save(
                    db,
                    {
                        "id": id,
                        "pedido_id": body.pedido_id,
                        "motivo": body.motivo,
                        "estado": "pendiente",
                        "creado_en": now(),
                        "decision": None,
                        "reembolso": None,
                    },
                    201,
                )
            return op.response()

    def solicitation_public(db, s, admin):
        r = db.execute(
            "SELECT * FROM reembolsos WHERE solicitud_id=?", (s["id"],)
        ).fetchone()
        decision = (
            None
            if s["estado"] == "pendiente"
            else {
                "id": s["decision_id"],
                "motivo": s["motivo_decision"],
                "fecha": s["decidida_en"],
            }
        )
        return {
            "id": s["id"],
            "pedido_id": s["pedido_id"],
            "motivo": s["motivo"],
            "estado": s["estado"],
            "creado_en": s["created_at"],
            "decision": decision,
            "reembolso": refund_public(db, r, admin) if r else None,
        }

    @app.get("/solicitudes-reembolso")
    async def solicitations(
        request: Request,
        pagina: int = 1,
        limite: int = 20,
        estado: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente", "administrador"})
        offset = pagination(pagina, limite)
        where, args = ["1=1"], []
        if user["rol"] == "cliente":
            where.append("cliente_id=?")
            args.append(user["cliente_id"])
        if estado:
            if estado not in {"pendiente", "aprobada", "rechazada"}:
                fail(422, "Estado de solicitud inválido")
            where.append("estado=?")
            args.append(estado)
        if desde or hasta:
            a, b = period(desde or "1970-01-01", hasta or "9998-12-31")
            where.extend(["created_at>=?", "created_at<?"])
            args.extend([a, b])
        clause = " AND ".join(where)
        with ctx.read() as db:
            total = db.execute(
                f"SELECT COUNT(*) FROM solicitudes_reembolso WHERE {clause}", args
            ).fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM solicitudes_reembolso WHERE {clause} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (*args, limite, offset),
            ).fetchall()
            return page(
                [
                    solicitation_public(db, s, user["rol"] == "administrador")
                    for s in rows
                ],
                total,
                pagina,
                limite,
            )

    @app.get("/solicitudes-reembolso/{id}")
    async def solicitation(id: int, request: Request):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"cliente", "administrador"})
        with ctx.read() as db:
            s = db.execute(
                "SELECT * FROM solicitudes_reembolso WHERE id=?", (id,)
            ).fetchone()
            if not s or (
                user["rol"] == "cliente" and s["cliente_id"] != user["cliente_id"]
            ):
                fail(404, "Solicitud no encontrada")
            return solicitation_public(db, s, user["rol"] == "administrador")

    @app.post("/solicitudes-reembolso/{id}/decisiones")
    async def decide(id: int, request: Request, body: Decision):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"administrador"})
        async with ctx.operation(
            request, f"decidir:{id}", user["id"], body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                s = db.execute(
                    "SELECT * FROM solicitudes_reembolso WHERE id=?", (id,)
                ).fetchone()
                if not s:
                    fail(404, "Solicitud no encontrada")
                if s["estado"] != "pendiente" and s["decision_id"] != op.id:
                    fail(409, "Solicitud ya decidida")
                if s["estado"] == "pendiente":
                    db.execute(
                        "UPDATE solicitudes_reembolso SET estado=?,decision_id=?,administrador_id=?,motivo_decision=?,decidida_en=? WHERE id=?",
                        (
                            "aprobada" if body.decision == "aprobar" else "rechazada",
                            op.id,
                            user["id"],
                            body.motivo,
                            now(),
                            id,
                        ),
                    )
                if body.decision == "rechazar":
                    op.save(db, {"id": id, "estado": "rechazada"})
                    return op.response()
            try:
                refund = await approved_solicitation(ctx, id)
            except HTTPException as exc:
                if exc.status_code < 500:
                    raise
                return JSONResponse(
                    {"id": id, "estado": "aprobada", "operacion_id": op.id},
                    status_code=202,
                    headers={"Retry-After": "2"},
                )
            with ctx.transaction() as db:
                op.save(db, {"id": id, "estado": "aprobada", "reembolso": refund}, 202)
            return op.response()

    @app.post("/reembolsos/{id}/reintentos")
    async def retry(id: int, request: Request, body: Empty):
        ctx.require_caller(request, "gateway")
        user = await ctx.actor(request, {"administrador"})
        async with ctx.operation(request, f"reintento:{id}", user["id"], {}) as op:
            if op.cached is not None:
                return op.response()
            result = await execute_refund(ctx, id, user["id"], retry=True)
            if result["estado"] != "pendiente":
                with ctx.transaction() as db:
                    op.save(db, result, 202)
            return JSONResponse(result, status_code=202)

    @app.post("/interno/reembolsos", status_code=202)
    async def technical(request: Request, body: TechnicalRefund):
        ctx.require_caller(request, "orders")
        with ctx.read() as db:
            p = db.execute("SELECT * FROM pagos WHERE id=?", (body.pago_id,)).fetchone()
        if not p or p["pedido_id"] != body.orden_id:
            fail(409, "Cobro no corresponde al pedido")
        o = await ctx.call("orders", "GET", f"/interno/ordenes/{body.orden_id}/cobro")
        if body.causa == "cancelacion_pagada" and (
            o["estado"] != "cancelado" or o["causa_cancelacion"] != "cancelacion_normal"
        ):
            fail(409, "Cancelación no autoriza esta devolución")
        if body.causa == "pago_tardio" and o["estado"] not in {"expirado", "cancelado"}:
            fail(409, "Pedido no vencido/cancelado")
        if body.causa == "cobro_duplicado" and (
            not o["pago_confirmado_id"] or o["pago_confirmado_id"] == body.pago_id
        ):
            fail(409, "No hay otro cobro aceptado")
        return await ensure_refund(ctx, body.pago_id, body.causa, body.operacion_id)

    @app.get("/interno/pagos/{id}/estado")
    async def internal_state(id: int, request: Request):
        ctx.require_caller(request, "orders")
        with ctx.read() as db:
            p = db.execute("SELECT * FROM pagos WHERE id=?", (id,)).fetchone()
            if not p:
                fail(404, "Pago no encontrado")
            return {
                **payment_public(p),
                "transaccion_id": p["transaccion_id"],
                "aprobado_en": p["aprobado_en"],
            }

    @app.post("/interno/pagos/consultas")
    async def batch(request: Request, body: PaymentBatch):
        ctx.require_caller(request, "graphql")
        user = await ctx.actor(request, {"cliente", "administrador", "cajero"})
        boxes = await boxes_for(user, request)
        results = []
        with ctx.read() as db:
            for id in dict.fromkeys(body.pedido_ids):
                if id <= 0:
                    fail(422, "ID inválido")
                p = db.execute(
                    "SELECT * FROM pagos WHERE pedido_id=? ORDER BY aceptado DESC,(estado='aprobado') DESC,id DESC LIMIT 1",
                    (id,),
                ).fetchone()
                if p:
                    permitted(user, p, boxes)
                r = db.execute(
                    "SELECT * FROM reembolsos WHERE pago_id=?",
                    (p["id"] if p else -1,),
                ).fetchone()
                results.append(
                    {
                        "pedido_id": id,
                        "pago": payment_public(p) if p else None,
                        "reembolso": refund_public(
                            db, r, user["rol"] == "administrador"
                        )
                        if r
                        else None,
                    }
                )
        return {"items": results}

    @app.get("/interno/reportes/movimientos")
    async def movements(request: Request, desde: str, hasta: str):
        ctx.require_caller(request, "graphql")
        await ctx.actor(request, {"administrador", "dueno"})
        start, end = period(desde, hasta)
        with ctx.read() as db:
            charged = db.execute(
                "SELECT COALESCE(SUM(monto),0) FROM pagos WHERE estado='aprobado' AND aprobado_en>=? AND aprobado_en<?",
                (start, end),
            ).fetchone()[0]
            refunded = db.execute(
                "SELECT COALESCE(SUM(monto_devuelto),0) FROM reembolsos WHERE estado='completado' AND completado_en>=? AND completado_en<?",
                (start, end),
            ).fetchone()[0]
        return {
            "total_cobrado": str(charged),
            "total_devuelto": str(refunded),
            "neto_cobrado": str(charged - refunded),
            "moneda": "CLP",
        }

    return app


app = create_app()
