import asyncio
import json

import pytest

from services.common import digest, later, now, period
from services.orders.backend_api import expire

pytestmark = pytest.mark.asyncio


async def test_catalog_and_private_boundary(stack):
    result = await stack.query(
        "{ catalogo { productos { items { id nombre precioFinal disponible } paginacion { total limite } } } }",
        role=None,
    )
    assert result.status_code == 200, result.text
    assert "errors" not in result.json(), result.text
    products = result.json()["data"]["catalogo"]["productos"]
    assert len(products["items"]) == 12 and products["paginacion"]["total"] == 20
    assert "stock" not in json.dumps(products)
    for path in (
        "/api/productos",
        "/api/perfil",
        "/api/ordenes",
        "/api/interno/auth/validar-sesion",
    ):
        assert (await stack.http.get(path)).status_code in {404, 405}
    response = await stack.ctx["gateway"].http.get("http://inventory:9000/productos")
    assert response.status_code == 403
    forged = await stack.http.post(
        "/api/productos",
        headers={"X-Role": "administrador", "X-Gateway-Secret": "forged"},
        json={},
    )
    assert forged.status_code == 401


async def test_register_verify_and_login(stack):
    body = {
        "nombres": "Ana",
        "apellidos": "Prueba",
        "rut": "12.345.678-5",
        "email": "ana@example.com",
        "telefono": "900000000",
        "direccion": "Calle ficticia",
        "comuna_id": 1,
        "provincia": "Santiago",
        "region": "Metropolitana",
        "fecha_nacimiento": "2000-01-01",
        "sexo": "No especificado",
    }
    r = await stack.http.post(
        "/api/registro", json=body, headers={"Idempotency-Key": "registro-ana"}
    )
    assert r.status_code == 201, r.text
    cid = r.json()["cliente_id"]
    assert "codigo" not in r.text
    with stack.ctx["clients"].read() as db:
        message = db.execute(
            "SELECT cuerpo FROM mensajes_simulados WHERE destinatario='ana@example.com'"
        ).fetchone()[0]
        code = message.split("codigo=")[1]
        assert db.execute(
            "SELECT codigo_hash FROM clientes WHERE id=?", (cid,)
        ).fetchone()[0] == digest(code)
    v = await stack.http.post(
        "/api/clientes/verificar-correo",
        json={"cliente_id": cid, "codigo": code, "password": "Clave-segura-123"},
        headers={"Idempotency-Key": "verificar-ana"},
    )
    assert v.status_code == 200, v.text
    login = await stack.http.post(
        "/api/login",
        json={"username": "ana@example.com", "password": "Clave-segura-123"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["token_type"] == "bearer"
    token = login.json()["access_token"]
    assert (
        await stack.http.post(
            "/api/logout", headers={"Authorization": "Bearer " + token}
        )
    ).status_code == 200
    assert (
        await stack.http.post(
            "/api/graphql",
            headers={"Authorization": "Bearer " + token},
            json={"query": "{ perfil { id } }"},
        )
    ).status_code == 401


async def test_session_revoked_on_role_edit(stack):
    id = stack.users["despacho"]["id"]
    response = await stack.http.patch(
        f"/api/admin/usuarios/{id}",
        headers=stack.headers("administrador"),
        json={"activo": False},
    )
    assert response.status_code == 200, response.text
    denied = await stack.query("{ perfil { id rol } }", role="despacho")
    assert denied.status_code == 401


async def test_checkout_idempotency_and_ownership(stack):
    first = await stack.checkout(key="checkout-estable")
    second = await stack.checkout(key="checkout-estable")
    assert first == second and stack.stock() == 20
    with stack.ctx["orders"].read() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM ordenes WHERE checkout_completo=1"
            ).fetchone()[0]
            == 1
        )
    own = await stack.query(
        "query($id:ID!){pedido(id:$id){id estado total lineas{nombre precioUnitario}}}",
        variables={"id": first["id"]},
    )
    assert own.json()["data"]["pedido"]["total"] == first["total"]
    other = await stack.query(
        "query($id:ID!){pedido(id:$id){id total}}",
        role="otro",
        variables={"id": first["id"]},
    )
    assert other.json()["data"]["pedido"] is None
    assert other.json()["errors"][0]["extensions"]["code"] == "NOT_FOUND"


async def test_last_unit_concurrent_checkouts(stack):
    with stack.ctx["inventory"].transaction() as db:
        db.execute("UPDATE productos SET stock=1 WHERE id=1")
    payload = {
        "direccion": {"calle": "Prueba", "numero": "1", "comuna_id": 1},
        "items": [{"producto_id": 1, "cantidad": 1}],
    }
    responses = await asyncio.gather(
        *(
            stack.http.post("/api/ordenes", json=payload, headers=stack.headers(role))
            for role in ("cliente", "otro")
        )
    )
    assert sorted(r.status_code for r in responses) == [201, 409], [
        r.text for r in responses
    ]
    with stack.ctx["inventory"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM reservas").fetchone()[0] == 1
    assert stack.stock() == 1


async def test_combo_and_product_demand_is_atomic(stack):
    with stack.ctx["inventory"].transaction() as db:
        db.execute("UPDATE productos SET stock=1 WHERE id=1")
    payload = {
        "direccion": {"calle": "Prueba", "numero": "1", "comuna_id": 1},
        "items": [{"producto_id": 1, "cantidad": 1}, {"combo_id": 1, "cantidad": 1}],
    }
    r = await stack.http.post("/api/ordenes", json=payload, headers=stack.headers())
    assert r.status_code == 409, r.text
    with stack.ctx["inventory"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM reservas").fetchone()[0] == 0


async def test_payment_sale_receipt_and_dispatch(stack):
    order = await stack.checkout()
    await stack.pay(order)
    assert stack.stock() == 19 and stack.order(order["id"])["estado"] == "pagado"
    with stack.ctx["orders"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 1
        assert (
            db.execute(
                "SELECT COUNT(*) FROM comprobantes WHERE estado_envio='simulado'"
            ).fetchone()[0]
            == 1
        )
    for route, state in (
        ("preparacion", "preparando"),
        ("envios", "enviado"),
        ("entregas", "entregado"),
    ):
        r = await stack.http.post(
            f"/api/ordenes/{order['id']}/{route}",
            headers=stack.headers("despacho"),
            json={},
        )
        assert r.status_code == 200 and r.json()["estado"] == state, r.text
    detail = await stack.query(
        "query($id:ID!){pedido(id:$id){estado pago{estado monto} comprobante{numero estadoEnvio} historial{items{estado}}}}",
        variables={"id": order["id"]},
    )
    assert "errors" not in detail.json(), detail.text
    assert detail.json()["data"]["pedido"]["estado"] == "entregado"


async def test_duplicate_notices_do_not_duplicate_effects(stack):
    order = await stack.checkout()
    pay = await stack.pay(order)
    again = await stack.http.post(
        pay["checkout_url"] + "/resultado", json={"estado": "aprobado"}
    )
    assert again.status_code == 200 and again.json()["aviso_entregado"]
    assert stack.stock() == 19
    with stack.ctx["orders"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM comprobantes").fetchone()[0] == 1
    with stack.ctx["payments"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM eventos_proveedor").fetchone()[0] == 1


async def test_rejected_payment_allows_new_attempt_without_extension(stack):
    order = await stack.checkout()
    rejected = await stack.pay(order, "rechazado")
    approved = await stack.pay(order)
    assert rejected["id"] != approved["id"]
    assert stack.order(order["id"])["vence_en"] == order["vence_en"]
    assert stack.order(order["id"])["estado"] == "pagado"


async def test_unpaid_cancellation_releases_without_adding_stock(stack):
    order = await stack.checkout()
    p = await stack.http.post(
        f"/api/ordenes/{order['id']}/preparacion",
        headers=stack.headers("despacho"),
        json={},
    )
    assert p.status_code == 409
    response = await stack.http.post(
        f"/api/ordenes/{order['id']}/cancelaciones",
        headers=stack.headers(key="cancelar-estable"),
        json={"motivo": "Cambio de plan"},
    )
    assert response.status_code == 200, response.text
    assert stack.stock() == 20
    with stack.ctx["inventory"].read() as db:
        assert (
            db.execute(
                "SELECT estado FROM reservas WHERE id=?", (order["reserva_id"],)
            ).fetchone()[0]
            == "liberada"
        )


async def test_paid_cancellation_restores_and_refunds_once(stack):
    order = await stack.checkout()
    await stack.pay(order)
    headers = stack.headers(key="cancelar-pagado")
    for _ in range(2):
        r = await stack.http.post(
            f"/api/ordenes/{order['id']}/cancelaciones",
            headers=headers,
            json={"motivo": "No continuar"},
        )
        assert r.status_code == 200, r.text
    assert stack.stock() == 20
    with stack.ctx["payments"].read() as db:
        refund = db.execute("SELECT * FROM reembolsos").fetchone()
        assert (
            refund["estado"] == "completado"
            and refund["monto_devuelto"] == order["total"]
        )
        assert db.execute("SELECT COUNT(*) FROM intentos_reembolso").fetchone()[0] == 1


async def test_cancel_prepare_race_has_single_winner(stack):
    order = await stack.checkout()
    await stack.pay(order)
    cancel, prepare = await asyncio.gather(
        stack.http.post(
            f"/api/ordenes/{order['id']}/cancelaciones",
            headers=stack.headers(),
            json={"motivo": "Cancelar"},
        ),
        stack.http.post(
            f"/api/ordenes/{order['id']}/preparacion",
            headers=stack.headers("despacho"),
            json={},
        ),
    )
    assert sorted([cancel.status_code, prepare.status_code]) == [200, 409], (
        cancel.text,
        prepare.text,
    )
    assert stack.order(order["id"])["estado"] in {"cancelado", "preparando"}


async def test_late_payment_refunds_without_sale_or_consumption(stack):
    order = await stack.checkout()
    pay = await stack.http.post(
        "/api/pagos", headers=stack.headers(), json={"orden_id": order["id"]}
    )
    assert pay.status_code == 201
    with stack.ctx["inventory"].transaction() as db:
        db.execute("UPDATE reservas SET vence_en=?", (later(-60),))
    with stack.ctx["orders"].transaction() as db:
        db.execute("UPDATE ordenes SET vence_en=?", (later(-60),))
    await expire(stack.ctx["orders"], order["id"])
    response = await stack.http.post(
        pay.json()["checkout_url"] + "/resultado", json={"estado": "aprobado"}
    )
    assert response.json()["aviso_entregado"]
    assert stack.order(order["id"])["estado"] == "expirado" and stack.stock() == 20
    with stack.ctx["orders"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 0
    with stack.ctx["payments"].read() as db:
        assert db.execute("SELECT estado FROM reembolsos").fetchone()[0] == "completado"


@pytest.mark.parametrize(
    "stage,expected",
    [("preparando", "cancelado"), ("enviado", "enviado"), ("entregado", "entregado")],
)
async def test_exceptional_refund_respects_operational_stage(stack, stage, expected):
    order = await stack.checkout()
    await stack.pay(order)
    for route in (
        ["preparacion"]
        + (["envios"] if stage in {"enviado", "entregado"} else [])
        + (["entregas"] if stage == "entregado" else [])
    ):
        r = await stack.http.post(
            f"/api/ordenes/{order['id']}/{route}",
            headers=stack.headers("despacho"),
            json={},
        )
        assert r.status_code == 200, r.text
    request = await stack.http.post(
        "/api/solicitudes-reembolso",
        headers=stack.headers(),
        json={
            "pedido_id": order["id"],
            "motivo": "Antecedentes textuales del problema",
        },
    )
    assert request.status_code == 201, request.text
    decision = await stack.http.post(
        f"/api/solicitudes-reembolso/{request.json()['id']}/decisiones",
        headers=stack.headers("administrador"),
        json={"decision": "aprobar", "motivo": "Excepción autorizada"},
    )
    assert decision.status_code == 202, decision.text
    assert decision.json()["reembolso"]["estado"] == "completado"
    assert stack.order(order["id"])["estado"] == expected and stack.stock() == 19
    if stage == "enviado":
        delivery = await stack.http.post(
            f"/api/ordenes/{order['id']}/entregas",
            headers=stack.headers("despacho"),
            json={},
        )
        assert delivery.status_code == 200


async def test_refund_failure_manual_retry_preserves_process_and_stock(stack):
    order = await stack.checkout()
    await stack.pay(order)
    with stack.ctx["simulator"].transaction() as db:
        db.execute("UPDATE transacciones SET fallos_reembolso=1")
    r = await stack.http.post(
        f"/api/ordenes/{order['id']}/cancelaciones",
        headers=stack.headers(),
        json={"motivo": "Cancelar antes de preparar"},
    )
    assert r.status_code == 200, r.text
    with stack.ctx["payments"].read() as db:
        refund = dict(db.execute("SELECT * FROM reembolsos").fetchone())
        assert refund["estado"] == "fallido"
    key = stack.headers("administrador", "reintento-estable")
    for _ in range(2):
        retried = await stack.http.post(
            f"/api/reembolsos/{refund['id']}/reintentos", headers=key, json={}
        )
        assert retried.status_code == 202, retried.text
        assert retried.json()["estado"] == "completado"
    assert stack.stock() == 20
    with stack.ctx["payments"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM reembolsos").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM intentos_reembolso").fetchone()[0] == 2


async def test_lost_refund_response_reconciles_same_provider_operation(stack):
    order = await stack.checkout()
    await stack.pay(order)
    stack.router.lose_refund_response = True
    cancelled = await stack.http.post(
        f"/api/ordenes/{order['id']}/cancelaciones",
        headers=stack.headers(),
        json={"motivo": "Cancelar"},
    )
    assert cancelled.status_code == 200, cancelled.text
    with stack.ctx["payments"].read() as db:
        refund = db.execute("SELECT * FROM reembolsos").fetchone()
        assert refund["estado"] == "pendiente"
        rid = refund["id"]
    retried = await stack.http.post(
        f"/api/reembolsos/{rid}/reintentos",
        headers=stack.headers("administrador"),
        json={},
    )
    assert retried.json()["estado"] == "completado", retried.text
    with stack.ctx["simulator"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM devoluciones").fetchone()[0] == 1
    with stack.ctx["payments"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM intentos_reembolso").fetchone()[0] == 1


async def test_despacho_field_permissions_and_owner_scope(stack):
    order = await stack.checkout()
    await stack.pay(order)
    result = await stack.query(
        "query($id:ID!){pedido(id:$id){id estado total pago{monto} lineas{nombre precioUnitario}}}",
        role="despacho",
        variables={"id": order["id"]},
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["data"]["pedido"]["estado"] == "pagado"
    assert (
        data["data"]["pedido"]["total"] is None
        and data["data"]["pedido"]["pago"] is None
    )
    assert all(x["extensions"]["code"] == "FORBIDDEN" for x in data["errors"])
    owner = await stack.query(
        "query($id:ID!){pedido(id:$id){id}}",
        role="dueno",
        variables={"id": order["id"]},
    )
    assert owner.json()["data"]["pedido"] is None


async def test_optional_dependency_failure_keeps_historical_data(stack):
    order = await stack.checkout()
    await stack.pay(order)
    stack.router.offline.add("inventory")
    result = await stack.query(
        "query($id:ID!){pedido(id:$id){estado total lineas{nombre precioUnitario catalogoActual{nombre}}}}",
        variables={"id": order["id"]},
    )
    data = result.json()
    assert data["data"]["pedido"]["total"] == order["total"]
    assert data["data"]["pedido"]["lineas"][0]["catalogoActual"] is None
    assert data["errors"][0]["extensions"]["code"] == "DEPENDENCY_UNAVAILABLE"
    stack.router.offline.clear()
    stack.router.offline.add("payments")
    history = await stack.query("{misPedidos{items{id estado pago{estado}}}}")
    assert history.json()["data"]["misPedidos"]["items"][0]["estado"] == "pagado"
    assert history.json()["data"]["misPedidos"]["items"][0]["pago"] is None
    assert history.json()["errors"]


async def test_report_negative_net_uses_movement_dates(stack):
    order = await stack.checkout()
    await stack.pay(order)
    await stack.http.post(
        f"/api/ordenes/{order['id']}/cancelaciones",
        headers=stack.headers(),
        json={"motivo": "Devolver"},
    )
    with stack.ctx["payments"].transaction() as db:
        db.execute("UPDATE pagos SET aprobado_en='2026-10-25T15:00:00+00:00'")
        db.execute("UPDATE reembolsos SET completado_en='2026-10-26T15:00:00+00:00'")
    result = await stack.query(
        '{reporteVentas(desde:"2026-10-26",hasta:"2026-10-26"){totalCobrado totalDevuelto netoCobrado ventas{items{id}}}}',
        role="dueno",
    )
    assert "errors" not in result.json(), result.text
    data = result.json()["data"]["reporteVentas"]
    assert data["totalCobrado"] == "0" and data["netoCobrado"] == str(-order["total"])
    a, b = period("2026-10-26", "2026-10-26")
    assert a == "2026-10-26T03:00:00+00:00" and b == "2026-10-27T03:00:00+00:00"


async def test_graphql_limits_and_finance_batching(stack):
    for _ in range(3):
        await stack.checkout()
    stack.router.calls.clear()
    result = await stack.query("{misPedidos{items{id pago{estado}} paginacion{total}}}")
    assert "errors" not in result.json(), result.text
    assert (
        sum(
            service == "payments" and path == "/interno/pagos/consultas"
            for service, method, path in stack.router.calls
        )
        == 1
    )
    excessive = await stack.query(
        "{" + " ".join(f"a{i}:perfil{{id}}" for i in range(2001)) + "}"
    )
    assert (
        excessive.status_code == 400
        and excessive.json()["errors"][0]["extensions"]["code"] == "QUERY_LIMIT"
    )
    page = await stack.query("{misPedidos(limite:51){paginacion{total}}}")
    assert page.status_code == 400, page.text
    deep = await stack.query(
        '{__type(name:"Query"){fields{type{ofType{ofType{ofType{ofType{name}}}}}}}}',
        role="administrador",
    )
    assert (
        deep.status_code == 400
        and deep.json()["errors"][0]["extensions"]["code"] == "QUERY_LIMIT"
    )


async def test_login_rate_limit_and_controlled_errors(stack):
    for _ in range(5):
        r = await stack.http.post(
            "/api/login", json={"username": "unknown", "password": "wrong"}
        )
        assert r.status_code == 401
    limited = await stack.http.post(
        "/api/login", json={"username": "unknown", "password": "wrong"}
    )
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    response = await stack.http.post(
        "/api/login", content="x" * 65537, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert "traceback" not in response.text.lower()


async def test_forged_payment_notice_cannot_confirm_payment(stack):
    order = await stack.checkout()
    await stack.pay(order, "pendiente")
    forged = {
        "evento_id": "forged",
        "tipo": "pago",
        "transaccion_id": "false",
        "estado": "aprobado",
        "monto": 1,
        "moneda": "CLP",
    }
    denied = await stack.http.post("/api/webhooks/pagos/simulado", json=forged)
    assert denied.status_code == 403
    assert stack.order(order["id"])["estado"] == "pendiente"
    manipulated = await stack.http.post(
        "/api/pagos",
        headers=stack.headers(),
        json={"orden_id": order["id"], "estado": "aprobado", "monto": 1},
    )
    assert manipulated.status_code == 422


async def test_product_deactivation_preserves_accepted_reservation(stack):
    order = await stack.checkout()
    r = await stack.http.delete(
        "/api/productos/1", headers=stack.headers("administrador")
    )
    assert r.status_code == 200
    await stack.pay(order)
    assert stack.order(order["id"])["estado"] == "pagado"
    catalog = await stack.query(
        "{catalogo(filtros:{productos:{productoId:1},combos:{comboId:1}}){productos{items{id}} combos{items{disponible}}}}",
        role=None,
    )
    assert catalog.json()["data"]["catalogo"]["productos"]["items"] == []
    assert (
        catalog.json()["data"]["catalogo"]["combos"]["items"][0]["disponible"] is False
    )


async def test_idempotency_payload_conflict(stack):
    await stack.checkout(key="same-key")
    response = await stack.http.post(
        "/api/ordenes",
        headers=stack.headers(key="same-key"),
        json={
            "direccion": {"calle": "Calle de prueba", "numero": "10", "comuna_id": 1},
            "items": [{"producto_id": 1, "cantidad": 2}],
        },
    )
    assert response.status_code == 409


async def test_duplicate_charge_refunded_but_accepted_payment_is_preserved(stack):
    order = await stack.checkout()
    old = await stack.pay(order, "rechazado")
    accepted = await stack.pay(order)
    # Falla del proveedor: después comunica que el intento anterior también cobró.
    with stack.ctx["simulator"].transaction() as db:
        db.execute(
            "UPDATE transacciones SET estado='aprobado',aprobado_en=? WHERE referencia=?",
            (now(), f"pago:{old['id']}"),
        )
    notice = await stack.http.post(
        old["checkout_url"] + "/resultado", json={"estado": "aprobado"}
    )
    assert notice.json()["aviso_entregado"]
    assert stack.stock() == 19
    with stack.ctx["payments"].read() as db:
        refund = db.execute("SELECT * FROM reembolsos").fetchone()
        assert (
            refund["pago_id"] == old["id"]
            and refund["causa"] == "cobro_duplicado"
            and refund["estado"] == "completado"
        )
    result = await stack.query(
        "query($id:ID!){pedido(id:$id){estado pago{id} reembolso{estado}}}",
        variables={"id": order["id"]},
    )
    assert result.json()["data"]["pedido"]["pago"]["id"] == str(accepted["id"]), (
        result.text
    )
    assert result.json()["data"]["pedido"]["reembolso"] is None


async def test_rejected_solicitation_requires_new_background_and_one_active(stack):
    order = await stack.checkout()
    await stack.pay(order)
    await stack.http.post(
        f"/api/ordenes/{order['id']}/preparacion",
        headers=stack.headers("despacho"),
        json={},
    )
    body = {"pedido_id": order["id"], "motivo": "Primeros antecedentes"}
    first = await stack.http.post(
        "/api/solicitudes-reembolso", headers=stack.headers(), json=body
    )
    duplicate = await stack.http.post(
        "/api/solicitudes-reembolso",
        headers=stack.headers(),
        json={**body, "motivo": "Segundos antecedentes"},
    )
    assert duplicate.status_code == 409
    decision = await stack.http.post(
        f"/api/solicitudes-reembolso/{first.json()['id']}/decisiones",
        headers=stack.headers("administrador"),
        json={"decision": "rechazar", "motivo": "No se acredita el motivo"},
    )
    assert decision.status_code == 200
    repeated = await stack.http.post(
        "/api/solicitudes-reembolso", headers=stack.headers(), json=body
    )
    assert repeated.status_code == 409
    new = await stack.http.post(
        "/api/solicitudes-reembolso",
        headers=stack.headers(),
        json={**body, "motivo": "Nuevos antecedentes"},
    )
    assert new.status_code == 201


async def test_cashier_disabled_blocks_new_charge_but_existing_payment_finishes(stack):
    existing, other = await stack.checkout(), await stack.checkout()
    payment = await stack.http.post(
        "/api/pagos", headers=stack.headers(), json={"orden_id": existing["id"]}
    )
    disabled = await stack.http.patch(
        f"/api/admin/usuarios/{stack.users['cajero']['id']}",
        headers=stack.headers("administrador"),
        json={"activo": False},
    )
    assert disabled.status_code == 200
    blocked = await stack.http.post(
        "/api/pagos", headers=stack.headers(), json={"orden_id": other["id"]}
    )
    assert blocked.status_code == 409
    await stack.http.post(
        payment.json()["checkout_url"] + "/resultado", json={"estado": "aprobado"}
    )
    assert stack.order(existing["id"])["estado"] == "pagado"


async def test_standard_typename_is_allowed_in_public_graphql(stack):
    response = await stack.query("{__typename catalogo{__typename}}", role=None)
    assert response.json()["data"]["__typename"] == "Query", response.text


async def test_checkout_total_overflow_does_not_hold_stock(stack):
    from services.common import MAX_MONEY

    with stack.ctx["inventory"].transaction() as db:
        db.execute(
            "UPDATE productos SET precio=?,precio_oferta=NULL WHERE id=1",
            (MAX_MONEY,),
        )
    for quantity in (1, 2):
        for _ in range(2):
            response = await stack.http.post(
                "/api/ordenes",
                headers=stack.headers(key=f"overflow-{quantity}"),
                json={
                    "direccion": {"calle": "Prueba", "numero": "1", "comuna_id": 1},
                    "items": [{"producto_id": 1, "cantidad": quantity}],
                },
            )
            assert response.status_code == 422, response.text
        with stack.ctx["inventory"].read() as db:
            assert db.execute("SELECT COUNT(*) FROM reservas").fetchone()[0] == 0
    result = await stack.query("{misPedidos{items{id} paginacion{total}}}")
    assert result.json()["data"]["misPedidos"]["paginacion"]["total"] == 0


async def test_payment_notice_is_retried_explicitly_after_dependency_failure(stack):
    order = await stack.checkout()
    payment = await stack.http.post(
        "/api/pagos", headers=stack.headers(), json={"orden_id": order["id"]}
    )
    url = payment.json()["checkout_url"] + "/resultado"
    stack.router.offline.add("orders")
    failed = await stack.http.post(url, json={"estado": "aprobado"})
    assert failed.json()["aviso_entregado"] is False
    assert stack.order(order["id"])["estado"] == "pendiente"
    stack.router.offline.clear()
    repeated = await stack.http.post(url, json={"estado": "aprobado"})
    assert repeated.json()["aviso_entregado"] is True
    assert stack.order(order["id"])["estado"] == "pagado"
    with stack.ctx["orders"].read() as db:
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 1


async def test_gateway_ignores_browser_identity_headers_and_uses_auth(stack):
    headers = {
        **stack.headers(),
        "X-Authenticated-User-ID": str(stack.users["administrador"]["id"]),
        "X-Authenticated-Roles": "administrador",
        "X-Authenticated-User": "forjado",
    }
    denied = await stack.http.post("/api/productos", headers=headers, json={})
    assert denied.status_code == 403
    result = await stack.http.post(
        "/api/graphql", headers=headers, json={"query": "{perfil{identificador rol}}"}
    )
    assert result.json()["data"]["perfil"]["rol"] == "cliente"
    assert result.json()["data"]["perfil"]["identificador"] == "cliente@example.com"
    assert any(
        service == "auth" and path == "/introspect"
        for service, _, path in stack.router.calls
    )
    # La sesión nunca se transmite a los servicios privados como un Bearer ni X-User-Session.
    direct = await stack.ctx["gateway"].http.post(
        "http://auth:8100/introspect", json={"token": stack.users["cliente"]["token"]}
    )
    assert direct.status_code == 403
