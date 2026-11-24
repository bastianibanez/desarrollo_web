"""Auth Service: login, introspect y logout, siguiendo el ejemplo del profesor."""

import os
import secrets

from fastapi import Depends, Header, HTTPException, Request
from pydantic import Field

from services.common import (
    Context,
    application,
    correlation,
    digest,
    fail,
    later,
    now,
    password_matches,
)
from services.dto import DTO, Login


class IntrospectionRequest(DTO):
    token: str = Field(min_length=1, max_length=256)


def session_ttl():
    value = os.getenv("AUTH_SESSION_TTL_SECONDS", "28800")
    if not value.isdecimal() or not 60 <= int(value) <= 86400:
        raise RuntimeError("AUTH_SESSION_TTL_SECONDS debe estar entre 60 y 86400")
    return int(value)


def create_app(ctx=None):
    ctx = ctx or Context("auth")
    app = application(ctx)
    ttl = session_ttl()

    def verify_gateway(x_gateway_auth_secret: str = Header(default="")):
        if not secrets.compare_digest(
            x_gateway_auth_secret, ctx.keys["incoming"]["gateway"]
        ):
            fail(403, "Gateway no autorizado")

    @app.post("/login", dependencies=[Depends(verify_gateway)])
    async def login(request: Request, body: Login):
        ctx.require_caller(request, "gateway")
        try:
            user = await ctx.call(
                "clients",
                "POST",
                "/interno/auth/credenciales",
                body={"username": body.username.lower()},
                headers=correlation(request),
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                ctx.event(request, "login_rechazado", motivo="credenciales")
                fail(401, "Credenciales inválidas")
            raise
        if not password_matches(body.password, user["password_hash"]):
            ctx.event(request, "login_rechazado", motivo="credenciales")
            fail(401, "Credenciales inválidas")
        if not user["habilitado"]:
            ctx.event(request, "login_rechazado", motivo="cuenta_inactiva")
            fail(403, "Cuenta no verificada o inactiva")
        token = secrets.token_urlsafe(32)
        with ctx.transaction() as db:
            db.execute(
                "INSERT INTO sesiones VALUES(?,?,?,?,?)",
                (digest(token), user["id"], user["version"], now(), later(ttl)),
            )
        ctx.event(request, "login_ok", user_id=user["id"])
        return {"access_token": token, "token_type": "bearer", "expires_in": ttl}

    @app.post("/introspect", dependencies=[Depends(verify_gateway)])
    async def introspect(request: Request, body: IntrospectionRequest):
        ctx.require_caller(request, "gateway")
        with ctx.read() as db:
            session = db.execute(
                "SELECT * FROM sesiones WHERE token_hash=?", (digest(body.token),)
            ).fetchone()
        if not session:
            ctx.event(request, "sesion_inactiva", motivo="inexistente")
            return {"active": False}
        if session["expira_at"] <= now():
            ctx.event(request, "sesion_inactiva", motivo="expirada")
            return {"active": False}
        try:
            user = await ctx.call(
                "clients",
                "GET",
                f"/interno/usuarios/{session['usuario_id']}",
                headers=correlation(request),
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                return {"active": False}
            raise
        if not user["habilitado"] or session["version_cuenta"] != user["version"]:
            ctx.event(
                request,
                "sesion_inactiva",
                motivo="version" if user["habilitado"] else "deshabilitada",
            )
            with ctx.transaction() as db:
                db.execute(
                    "DELETE FROM sesiones WHERE token_hash=?", (digest(body.token),)
                )
            return {"active": False}
        ctx.event(request, "token_valido", user_id=user["id"], rol=user["rol"])
        return {
            "active": True,
            "user_id": user["id"],
            "username": user["identificador"],
            "roles": [user["rol"]],
            "cliente_id": user["cliente_id"],
            "email_verificado_at": user["email_verificado_at"],
            "expires_at": session["expira_at"],
        }

    @app.post("/logout", dependencies=[Depends(verify_gateway)])
    async def logout(request: Request, body: IntrospectionRequest):
        ctx.require_caller(request, "gateway")
        with ctx.transaction() as db:
            db.execute("DELETE FROM sesiones WHERE token_hash=?", (digest(body.token),))
        ctx.event(request, "logout")
        return {"message": "Sesión finalizada"}

    return app


app = create_app()
