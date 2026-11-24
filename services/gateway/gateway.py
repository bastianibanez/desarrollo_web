import json
import os
import time

import httpx
from fastapi import Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.common import (
    Context,
    application,
    correlation,
    digest,
    encode,
    fail,
    identity_headers,
    linea,
)
from services.gateway.routes import ROUTES, SIMULATOR_ROUTES


class RateLimiter:
    """Contadores por minuto en memoria, suficientes para la demo local."""

    def __init__(self):
        self.minute = None
        self.counts = {}

    def allows(self, key, limit, add=True):
        minute = int(time.monotonic() // 60)
        if minute != self.minute:
            self.minute = minute
            self.counts.clear()
        if self.counts.get(key, 0) >= limit:
            return False
        if add:
            self.failure(key)
        return True

    def failure(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1


def cors_origins():
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


async def login_user(request):
    try:
        data = json.loads(await request.body())
    except ValueError:
        return ""
    username = data.get("username") if isinstance(data, dict) else None
    return username.strip().lower()[:254] if isinstance(username, str) else ""


def create_app(ctx=None):
    ctx = ctx or Context("gateway")
    app = application(ctx, external=True)
    security = HTTPBearer(auto_error=False)
    bearer_dependency = Depends(security)
    rate = RateLimiter()
    app.state.rate = rate
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    def limit(request, scope, key, maximum, add=True):
        if not rate.allows(key, maximum, add):
            ctx.event(request, "limite_excedido", scope=scope)
            raise HTTPException(
                429, "Límite de solicitudes excedido", headers={"Retry-After": "60"}
            )

    async def authenticate_client(request, credentials):
        if credentials is None:
            ctx.event(request, "auth_denegado", motivo="sin_token")
            raise HTTPException(401, "Bearer token requerido")
        identity = await ctx.call(
            "auth",
            "POST",
            "/introspect",
            body={"token": credentials.credentials},
            headers=correlation(request),
        )
        if not identity.get("active"):
            ctx.event(request, "auth_denegado", motivo="token_inactivo")
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
            login_key = None
            if public_path == "/login":
                login_key = ("login", ip, await login_user(request))
                limit(request, "login", login_key, 5, add=False)
            user = None
            if roles is not None or (public_path == "/graphql" and credentials):
                user = await authenticate_client(request, credentials)
                if roles and user["rol"] not in roles:
                    ctx.event(request, "prohibido", rol=user["rol"], route=public_path)
                    raise HTTPException(403, "Perfil sin permiso")
                ctx.event(
                    request,
                    "autorizado",
                    user_id=user["id"],
                    rol=user["rol"],
                    route=public_path,
                )
            request.state.user = user
            if user:
                limit(request, "user", ("user", user["id"]), 60)
            else:
                limit(request, "ip", ("ip", ip), 120)
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
                body = encode({"token": credentials.credentials}).encode()
                headers["content-type"] = "application/json"
            linea("->", target, method, public_path)
            started = time.monotonic()
            try:
                upstream = await ctx.http.request(
                    method,
                    ctx.url(target) + path,
                    content=body,
                    params=request.query_params,
                    headers=headers,
                    timeout=15 if target == "graphql" else 10,
                )
            except httpx.TimeoutException:
                ctx.upstream(
                    target,
                    method,
                    public_path,
                    "timeout",
                    started,
                )
                fail(
                    504,
                    "El servicio tardó demasiado en responder",
                    "DEPENDENCY_TIMEOUT",
                )
            except httpx.RequestError:
                ctx.upstream(
                    target,
                    method,
                    public_path,
                    "unavailable",
                    started,
                )
                fail(503, "Servicio no disponible", "DEPENDENCY_UNAVAILABLE")
            if login_key and upstream.status_code in {401, 403}:
                rate.failure(login_key)
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
