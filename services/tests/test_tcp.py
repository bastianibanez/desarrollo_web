"""Prueba con sockets HTTP reales y vencimiento automático, sin necesitar Docker."""

import asyncio
import socket

import httpx
import pytest
import uvicorn

from services.common import Context, later
from services.tests.conftest import FACTORIES, Stack
from services.tests.node_runtime import node_server


@pytest.mark.asyncio
async def test_complete_backend_over_real_http(stack):
    sockets, ports = {}, {}
    for name in FACTORIES:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        sock.setblocking(False)
        sockets[name], ports[name] = sock, sock.getsockname()[1]
    contexts = {
        name: Context(name, stack.ctx[name].data_dir, stack.ctx[name].keys)
        for name in FACTORIES
    }
    for ctx in contexts.values():
        ctx.url = lambda target: f"http://127.0.0.1:{ports[target]}"
    servers = {
        name: uvicorn.Server(
            uvicorn.Config(
                FACTORIES[name](contexts[name]), log_level="critical", access_log=False
            )
        )
        for name in FACTORIES
    }
    tasks = [
        asyncio.create_task(server.serve(sockets=[sockets[name]]))
        for name, server in servers.items()
    ]
    try:
        for _ in range(100):
            if all(server.started for server in servers.values()):
                break
            await asyncio.sleep(0.05)
        assert all(server.started for server in servers.values())
        async with (
            node_server(
                stack.ctx["graphql"].data_dir / "tcp-node",
                stack.ctx["graphql"].keys,
                {name: f"http://127.0.0.1:{port}" for name, port in ports.items()},
            ) as graphql_url,
            httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{ports['gateway']}", timeout=15
            ) as http,
        ):
            ports["graphql"] = int(graphql_url.rsplit(":", 1)[1])
            live = Stack(contexts, stack.router, http, stack.users)
            order = await live.checkout()
            await live.pay(order)
            for _ in range(100):
                if live.order(order["id"])["estado"] == "pagado":
                    break
                await asyncio.sleep(0.05)
            assert live.order(order["id"])["estado"] == "pagado"
            result = await live.query(
                "query($id:ID!){pedido(id:$id){estado total pago{estado} comprobante{numero} lineas{nombre catalogoActual{nombre}}}}",
                variables={"id": order["id"]},
            )
            assert "errors" not in result.json(), result.text
            for path in ("preparacion", "envios", "entregas"):
                response = await http.post(
                    f"/api/ordenes/{order['id']}/{path}",
                    headers=live.headers("despacho"),
                    json={},
                )
                assert response.status_code == 200, response.text
            assert live.order(order["id"])["estado"] == "entregado"
            pending = await live.checkout()
            with contexts["inventory"].transaction() as db:
                db.execute(
                    "UPDATE reservas SET vence_en=? WHERE id=?",
                    (later(-60), pending["reserva_id"]),
                )
            with contexts["orders"].transaction() as db:
                db.execute(
                    "UPDATE ordenes SET vence_en=? WHERE id=?",
                    (later(-60), pending["id"]),
                )
            for _ in range(100):
                if live.order(pending["id"])["estado"] == "expirado":
                    break
                await asyncio.sleep(0.05)
            assert live.order(pending["id"])["estado"] == "expirado"
            for name in (
                "auth",
                "clients",
                "inventory",
                "orders",
                "payments",
                "graphql",
                "simulator",
            ):
                denied = await http.get(f"http://127.0.0.1:{ports[name]}/openapi.json")
                assert denied.status_code == 403
    finally:
        for server in servers.values():
            server.should_exit = True
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=10
        )
        for sock in sockets.values():
            sock.close()
