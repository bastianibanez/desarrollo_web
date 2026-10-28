"""Auth Service: login, introspect y logout, siguiendo el ejemplo del profesor."""

import secrets

from fastapi import Depends, Header, HTTPException, Request
from pydantic import Field

from services.common import (
    Context,
    application,
    digest,
    fail,
    later,
    now,
    password_matches,
)
from services.dto import DTO, Login


class IntrospectionRequest(DTO):
    token: str = Field(min_length=1, max_length=256)


def create_app(ctx=None):
    ctx = ctx or Context("auth")
    app = application(ctx)

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
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                fail(401, "Credenciales inválidas")
            raise
        if not password_matches(body.password, user["password_hash"]):
            fail(401, "Credenciales inválidas")
        if not user["habilitado"]:
            fail(403, "Cuenta no verificada o inactiva")
        token = secrets.token_urlsafe(32)
        with ctx.transaction() as db:
            db.execute(
                "INSERT INTO sesiones VALUES(?,?,?,?,?)",
                (digest(token), user["id"], user["version"], now(), later(28800)),
            )
        return {"access_token": token, "token_type": "bearer", "expires_in": 28800}

    @app.post("/introspect", dependencies=[Depends(verify_gateway)])
    async def introspect(request: Request, body: IntrospectionRequest):
        ctx.require_caller(request, "gateway")
        with ctx.read() as db:
            session = db.execute(
                "SELECT * FROM sesiones WHERE token_hash=? AND expira_at>?",
                (digest(body.token), now()),
            ).fetchone()
        if not session:
            return {"active": False}
        try:
            user = await ctx.call(
                "clients", "GET", f"/interno/usuarios/{session['usuario_id']}"
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                return {"active": False}
            raise
        if not user["habilitado"] or session["version_cuenta"] != user["version"]:
            with ctx.transaction() as db:
                db.execute(
                    "DELETE FROM sesiones WHERE token_hash=?", (digest(body.token),)
                )
            return {"active": False}
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
        return {"message": "Sesión finalizada"}

    return app


app = create_app()
