import time

import httpx
from fastapi import Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.common import Context, application, digest, identity_headers
from services.gateway.routes import ROUTES, SIMULATOR_ROUTES


class RateLimiter:
    """Contadores por minuto en memoria, suficientes para la demo local."""

    def __init__(self):
        self.minute = None
        self.counts = {}

    def check(self, key, limit, add=True):
        minute = int(time.monotonic() // 60)
        if minute != self.minute:
            self.minute = minute
            self.counts.clear()
        if self.counts.get(key, 0) >= limit:
            raise HTTPException(
                429, "Límite de solicitudes excedido", headers={"Retry-After": "60"}
            )
        if add:
            self.failure(key)

    def failure(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1


def create_app(ctx=None):
    ctx = ctx or Context("gateway")
    app = application(ctx, external=True)
    security = HTTPBearer(auto_error=False)
    bearer_dependency = Depends(security)
    rate = RateLimiter()
    app.state.rate = rate
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    async def authenticate_client(credentials):
        if credentials is None:
            raise HTTPException(401, "Bearer token requerido")
        identity = await ctx.call(
            "auth", "POST", "/introspect", body={"token": credentials.credentials}
        )
        if not identity.get("active"):
            raise HTTPException(401, "Token inválido o expirado")
        return {
            "id": identity["user_id"],
            "identificador": identity["username"],
            "rol": identity["roles"][0],
            "cliente_id": identity["cliente_id"],
            "email_verificado_at": identity["email_verificado_at"],
        }

    def endpoint(method, public_path, target, roles, simulator=False):
        async def proxy(
            request: Request,
            credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
        ):
            ip = request.client.host if request.client else "unknown"
            login = public_path == "/login"
            if login:
                rate.check(("login", ip), 5, add=False)
            user = None
            if roles is not None or (public_path == "/graphql" and credentials):
                user = await authenticate_client(credentials)
                if roles and user["rol"] not in roles:
                    raise HTTPException(403, "Perfil sin permiso")
            request.state.user = user
            rate.check(
                ("user", user["id"]) if user else ("ip", ip), 60 if user else 120
            )
            path = public_path
            for name, value in request.path_params.items():
                if name == "id" and (not value.isdecimal() or int(value) <= 0):
                    raise HTTPException(422, "ID inválido")
                # Los segmentos de ruta no pueden introducir otra ruta en el destino.
                if "/" in value or "\\" in value or value in {".", ".."}:
                    raise HTTPException(422, "Segmento inválido")
                path = path.replace("{" + name + "}", value)
            if simulator:
                path = path.removeprefix("/simulador/pagos")
            await ctx.load_keys()
            headers = {
                "X-Gateway-Secret": ctx.keys["outgoing"][target],
                **identity_headers(user),
                "X-Request-ID": request.state.request_id,
            }
            for key in (
                "content-type",
                "idempotency-key",
                "x-proveedor-timestamp",
                "x-proveedor-firma",
            ):
                if key in request.headers:
                    headers[key] = request.headers[key]
            if target == "auth":
                headers["X-Gateway-Auth-Secret"] = ctx.keys["outgoing"][target]
            body = await request.body()
            if public_path == "/logout":
                from services.common import encode

                body = encode({"token": credentials.credentials}).encode()
                headers["content-type"] = "application/json"
            try:
                upstream = await ctx.http.request(
                    method,
                    ctx.url(target) + path,
                    content=body,
                    params=request.query_params,
                    headers=headers,
                    timeout=15 if target == "graphql" else 10,
                )
            except httpx.RequestError:
                raise HTTPException(503, "Servicio no disponible") from None
            if login and upstream.status_code in {401, 403}:
                rate.failure(("login", ip))
            response_headers = {
                k: v
                for k, v in upstream.headers.items()
                if k.lower() in {"content-type", "retry-after", "content-disposition"}
            }
            return Response(
                upstream.content,
                status_code=upstream.status_code,
                headers=response_headers,
            )

        return proxy

    for method, path, target, roles in ROUTES:
        app.add_api_route(
            "/api" + path,
            endpoint(method, path, target, roles),
            methods=[method],
            name=f"{method} {path}",
            operation_id=digest(method + path)[:16],
            openapi_extra={
                "parameters": [
                    {
                        "name": "Idempotency-Key",
                        "in": "header",
                        "required": False,
                        "schema": {"type": "string"},
                    },
                ]
            },
        )
    for method, path, target, roles in SIMULATOR_ROUTES:
        app.add_api_route(
            path,
            endpoint(method, path, target, roles, True),
            methods=[method],
            include_in_schema=False,
        )
    return app


app = create_app()
