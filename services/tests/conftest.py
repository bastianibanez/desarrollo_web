import asyncio
import secrets
from contextlib import AsyncExitStack

import httpx
import pytest_asyncio
import uvicorn
from fastapi import FastAPI, Request, Response

from services.auth.auth_service import create_app as auth_app
from services.bootstrap import EDGES
from services.clients.backend_api import account
from services.clients.backend_api import create_app as clients_app
from services.common import Context, digest, later, now, password_hash
from services.gateway.gateway import create_app as gateway_app
from services.inventory.backend_api import create_app as inventory_app
from services.orders.backend_api import create_app as orders_app
from services.payments.backend_api import create_app as payments_app
from services.simulator.backend_api import create_app as simulator_app
from services.tests.node_runtime import free_port, node_server

FACTORIES = {
    "auth": auth_app,
    "clients": clients_app,
    "inventory": inventory_app,
    "orders": orders_app,
    "payments": payments_app,
    "simulator": simulator_app,
    "gateway": gateway_app,
}


class Router(httpx.AsyncBaseTransport):
    def __init__(self):
        self.apps = {}
        self.offline = set()
        self.lose_refund_response = False
        self.calls = []
        self.graphql_url = None
        self.tcp = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        service = request.url.host
        self.calls.append((service, request.method, request.url.path))
        if service in self.offline:
            raise httpx.ConnectError(
                "Simulated unavailable dependency", request=request
            )
        if service == "graphql":
            request.url = httpx.URL(self.graphql_url + request.url.raw_path.decode())
            return await self.tcp.handle_async_request(request)
        response = await httpx.ASGITransport(
            app=self.apps[service]
        ).handle_async_request(request)
        if (
            self.lose_refund_response
            and service == "simulator"
            and request.method == "POST"
            and request.url.path.endswith("/reembolsos")
        ):
            self.lose_refund_response = False
            await response.aread()
            raise httpx.ReadTimeout(
                "Response lost after provider commit", request=request
            )
        return response


class Stack:
    def __init__(self, contexts, router, http, users):
        self.ctx, self.router, self.http, self.users = contexts, router, http, users

    def headers(self, role="cliente", key=None):
        return {
            "Authorization": "Bearer " + self.users[role]["token"],
            "Idempotency-Key": key or secrets.token_hex(16),
        }

    async def checkout(self, role="cliente", items=None, key=None):
        response = await self.http.post(
            "/api/ordenes",
            headers=self.headers(role, key),
            json={
                "direccion": {
                    "calle": "Calle de prueba",
                    "numero": "10",
                    "comuna_id": 1,
                },
                "items": items or [{"producto_id": 1, "cantidad": 1}],
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    async def pay(self, order, outcome="aprobado"):
        response = await self.http.post(
            "/api/pagos", headers=self.headers(), json={"orden_id": order["id"]}
        )
        assert response.status_code == 201, response.text
        payment = response.json()
        result = await self.http.post(
            payment["checkout_url"] + "/resultado", json={"estado": outcome}
        )
        assert result.status_code == 200, result.text
        assert result.json()["aviso_entregado"], result.text
        return payment

    async def query(self, query, role="cliente", variables=None):
        return await self.http.post(
            "/api/graphql",
            headers=self.headers(role) if role else {},
            json={"query": query, "variables": variables},
        )

    def order(self, id):
        with self.ctx["orders"].read() as db:
            return dict(
                db.execute("SELECT * FROM ordenes WHERE id=?", (id,)).fetchone()
            )

    def stock(self, id=1):
        with self.ctx["inventory"].read() as db:
            return db.execute(
                "SELECT stock FROM productos WHERE id=?", (id,)
            ).fetchone()[0]


@pytest_asyncio.fixture
async def stack(tmp_path):
    credentials = {name: {"incoming": {}, "outgoing": {}} for name in EDGES}
    for source, destinations in EDGES.items():
        for destination in destinations:
            token = secrets.token_urlsafe(32)
            credentials[source]["outgoing"][destination] = token
            credentials[destination]["incoming"][source] = token
    hmac = secrets.token_urlsafe(32)
    credentials["payments"]["provider_hmac"] = credentials["simulator"][
        "provider_hmac"
    ] = hmac
    router = Router()
    contexts = {
        name: Context(name, tmp_path, credentials[name], router) for name in EDGES
    }
    for c in contexts.values():
        c.disable_workers = True
    router.apps = {name: factory(contexts[name]) for name, factory in FACTORIES.items()}
    async with AsyncExitStack() as lifespans:
        for app in router.apps.values():
            await lifespans.enter_async_context(app.router.lifespan_context(app))
        users = {}
        with contexts["clients"].transaction() as db:
            for role in (
                "administrador",
                "cajero",
                "despacho",
                "dueno",
                "cliente",
                "otro",
            ):
                client_id = None
                if role in {"cliente", "otro"}:
                    client_id = db.execute(
                        "INSERT INTO clientes(nombres,apellidos,rut,email,telefono,email_verificado_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            role,
                            "Prueba",
                            role,
                            role + "@example.com",
                            "900000000",
                            now(),
                            now(),
                            now(),
                        ),
                    ).lastrowid
                id = db.execute(
                    "INSERT INTO usuarios(cliente_id,identificador,password_hash,rol,created_at) VALUES(?,?,?,?,?)",
                    (
                        client_id,
                        role + "@example.com",
                        password_hash("Clave-de-prueba-123"),
                        "cliente" if role == "otro" else role,
                        now(),
                    ),
                ).lastrowid
                users[role] = {"id": id, "cliente_id": client_id}
        with contexts["clients"].read() as db:
            versions = {
                role: account(db, id=u["id"])["version"] for role, u in users.items()
            }
        with contexts["auth"].transaction() as db:
            for role, user in users.items():
                token = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO sesiones VALUES(?,?,?,?,?)",
                    (digest(token), user["id"], versions[role], now(), later(28800)),
                )
                user["token"] = token
        with contexts["orders"].transaction() as db:
            db.execute(
                "UPDATE cajas SET cajero_id=? WHERE id=1", (users["cajero"]["id"],)
            )
        # Puente HTTP de pruebas: Node utiliza las mismas APIs ASGI y permisos reales.
        bridge = FastAPI()

        @bridge.api_route(
            "/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
        )
        async def forward(service: str, path: str, request: Request):
            target = httpx.Request(
                request.method,
                f"http://{service}:9000/{path}",
                headers=request.headers,
                params=request.query_params,
                content=await request.body(),
            )
            result = await router.handle_async_request(target)
            return Response(
                await result.aread(),
                status_code=result.status_code,
                headers={
                    "content-type": result.headers.get(
                        "content-type", "application/json"
                    )
                },
            )

        port = free_port()
        server = uvicorn.Server(
            uvicorn.Config(
                bridge,
                host="127.0.0.1",
                port=port,
                log_level="critical",
                access_log=False,
            )
        )
        task = asyncio.create_task(server.serve())
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(0.01)
            async with node_server(
                tmp_path / "node",
                credentials["graphql"],
                {name: f"http://127.0.0.1:{port}/{name}" for name in FACTORIES},
            ) as url:
                router.graphql_url = url
                async with httpx.AsyncClient(
                    base_url="http://gateway", transport=router
                ) as http:
                    yield Stack(contexts, router, http, users)
        finally:
            server.should_exit = True
            await task
            await router.tcp.aclose()
