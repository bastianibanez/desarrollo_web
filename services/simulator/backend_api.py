"""Proveedor de prueba persistente. Ningún dinero real; separado de payments."""

import hashlib
import hmac
import json
import secrets
import time
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import Field

from services.common import Context, application, digest, fail, now
from services.dto import DTO


class Transaction(DTO):
    referencia: str = Field(min_length=1, max_length=128)
    monto: int = Field(ge=0, le=2_147_483_647)
    moneda: Literal["CLP"]


class Outcome(DTO):
    estado: Literal["aprobado", "rechazado", "pendiente"]
    enviar_aviso: bool = True


class Refund(DTO):
    monto: int = Field(ge=0, le=2_147_483_647)
    moneda: Literal["CLP"]


def public_transaction(r):
    return {
        "id": r["id"],
        "transaccion_id": r["id"],
        "monto": r["monto"],
        "moneda": r["moneda"],
        "estado": r["estado"],
        "aprobado_en": r["aprobado_en"],
    }


def create_app(ctx=None):
    ctx = ctx or Context("simulator")
    app = application(ctx)

    def checkout_token(id):
        return hmac.new(
            ctx.keys["provider_hmac"].encode(),
            f"checkout:{id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @app.post("/transacciones", status_code=201)
    async def transaction(request: Request, body: Transaction):
        ctx.require_caller(request, "payments")
        async with ctx.operation(
            request, "transaccion", "payments", body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                r = db.execute(
                    "SELECT * FROM transacciones WHERE referencia=?", (body.referencia,)
                ).fetchone()
                if r and (r["monto"] != body.monto or r["moneda"] != body.moneda):
                    fail(409, "Referencia con otro monto")
                if not r:
                    id = secrets.token_urlsafe(18)
                    db.execute(
                        "INSERT INTO transacciones(id,referencia,token_hash,monto,moneda,created_at) VALUES(?,?,?,?,?,?)",
                        (
                            id,
                            body.referencia,
                            digest(checkout_token(id)),
                            body.monto,
                            body.moneda,
                            now(),
                        ),
                    )
                    r = db.execute(
                        "SELECT * FROM transacciones WHERE id=?", (id,)
                    ).fetchone()
                op.save(
                    db,
                    {
                        **public_transaction(r),
                        "checkout_url": f"/simulador/pagos/checkout/{checkout_token(r['id'])}",
                    },
                    201,
                )
            return op.response()

    @app.get("/transacciones/{id}")
    async def state(id: str, request: Request):
        ctx.require_caller(request, "payments")
        with ctx.read() as db:
            r = db.execute("SELECT * FROM transacciones WHERE id=?", (id,)).fetchone()
        if not r:
            fail(404, "Transacción no encontrada")
        return public_transaction(r)

    @app.get("/checkout/{token}", response_class=HTMLResponse)
    async def checkout(token: str, request: Request):
        ctx.require_caller(request, "gateway")
        with ctx.read() as db:
            r = db.execute(
                "SELECT * FROM transacciones WHERE token_hash=?", (digest(token),)
            ).fetchone()
        if not r:
            fail(404, "Checkout no encontrado")
        # El token opaco delimita una transacción de demostración, sin poder cambiar su importe.
        return HTMLResponse(f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proveedor simulado</title><body><h1>Pago simulado Fit Express</h1><p>No se procesa dinero real.</p><p>CLP ${r["monto"]}</p>
<button onclick="resultado('aprobado')">Aprobar</button><button onclick="resultado('rechazado')">Rechazar</button><button onclick="resultado('pendiente')">Dejar pendiente</button><p id="estado"></p>
<script>async function resultado(estado){{const r=await fetch(location.pathname+'/resultado',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{estado}})}});document.getElementById('estado').textContent=JSON.stringify(await r.json());}}</script></body></html>""")

    @app.post("/checkout/{token}/resultado")
    async def outcome(token: str, request: Request, body: Outcome):
        ctx.require_caller(request, "gateway")
        with ctx.transaction() as db:
            r = db.execute(
                "SELECT * FROM transacciones WHERE token_hash=?", (digest(token),)
            ).fetchone()
            if not r:
                fail(404, "Checkout no encontrado")
            if r["estado"] != "pendiente" and r["estado"] != body.estado:
                fail(409, "Resultado terminal ya fijado")
            db.execute(
                "UPDATE transacciones SET estado=?,aprobado_en=CASE WHEN ?='aprobado' THEN COALESCE(aprobado_en,?) ELSE aprobado_en END WHERE id=?",
                (body.estado, body.estado, now(), r["id"]),
            )
            r = dict(
                db.execute(
                    "SELECT * FROM transacciones WHERE id=?", (r["id"],)
                ).fetchone()
            )
        delivered = False
        if body.enviar_aviso:
            payload = {
                "evento_id": f"pago:{r['id']}:{body.estado}",
                "tipo": "pago",
                "transaccion_id": r["id"],
                "estado": body.estado,
                "monto": r["monto"],
                "moneda": r["moneda"],
            }
            raw = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode()
            timestamp = str(int(time.time()))
            signature = hmac.new(
                ctx.keys["provider_hmac"].encode(),
                timestamp.encode() + b"." + raw,
                hashlib.sha256,
            ).hexdigest()
            try:
                await ctx.call(
                    "payments",
                    "POST",
                    "/webhooks/pagos/simulado",
                    body=payload,
                    headers={
                        "X-Proveedor-Timestamp": timestamp,
                        "X-Proveedor-Firma": signature,
                    },
                )
                delivered = True
            except HTTPException:
                # El resultado financiero se conserva; repetir esta misma acción reenvía el aviso.
                pass
        return {**public_transaction(r), "aviso_entregado": delivered, "simulado": True}

    @app.post("/transacciones/{id}/reembolsos", status_code=201)
    async def refund(id: str, request: Request, body: Refund):
        ctx.require_caller(request, "payments")
        async with ctx.operation(
            request, f"reembolso:{id}", "payments", body.model_dump()
        ) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                t = db.execute(
                    "SELECT * FROM transacciones WHERE id=?", (id,)
                ).fetchone()
                if not t or t["estado"] != "aprobado" or body.monto != t["monto"]:
                    fail(409, "Cobro no reembolsable")
                prior = db.execute(
                    "SELECT * FROM devoluciones WHERE transaccion_id=? AND estado='completado'",
                    (id,),
                ).fetchone()
                if prior:
                    fail(409, "Cobro ya devuelto")
                failed = t["fallos_reembolso"] > 0
                if failed:
                    db.execute(
                        "UPDATE transacciones SET fallos_reembolso=fallos_reembolso-1 WHERE id=?",
                        (id,),
                    )
                rid = secrets.token_urlsafe(18)
                completed = None if failed else now()
                result = {
                    "id": rid,
                    "transaccion_id": id,
                    "estado": "fallido" if failed else "completado",
                    "monto": body.monto,
                    "moneda": "CLP",
                    "completado_en": completed,
                }
                db.execute(
                    "INSERT INTO devoluciones VALUES(?,?,?,?,?,?,?)",
                    (
                        rid,
                        request.headers["idempotency-key"],
                        id,
                        body.monto,
                        result["estado"],
                        completed,
                        now(),
                    ),
                )
                op.save(db, result, 201)
            return op.response()

    @app.get("/reembolsos/{id}")
    async def refund_state(id: str, request: Request):
        ctx.require_caller(request, "payments")
        with ctx.read() as db:
            r = db.execute(
                "SELECT * FROM devoluciones WHERE id=? OR clave=?", (id, id)
            ).fetchone()
        if not r:
            fail(404, "Devolución no encontrada")
        return {
            "id": r["id"],
            "transaccion_id": r["transaccion_id"],
            "estado": r["estado"],
            "monto": r["monto"],
            "moneda": "CLP",
            "completado_en": r["completado_en"],
        }

    return app


app = create_app()
