import secrets

from fastapi import Request
from pydantic import Field

from services.common import (
    Context,
    application,
    current_user,
    digest,
    encode,
    fail,
    later,
    now,
    page,
    pagination,
    password_hash,
    private_fingerprint,
)
from services.dto import (
    DTO,
    ClientePatch,
    Funcionario,
    FuncionarioPatch,
    Registro,
    Verificar,
)


class Credenciales(DTO):
    username: str = Field(min_length=1, max_length=254)


def rut_normalizado(value):
    value = value.replace(".", "").replace(" ", "").upper()
    body, _, digit = value.rpartition("-")
    if not body.isdecimal() or not 1 <= len(body) <= 8:
        fail(422, "RUT inválido")
    rest = 11 - sum(int(n) * (2 + i % 6) for i, n in enumerate(reversed(body))) % 11
    expected = "0" if rest == 11 else "K" if rest == 10 else str(rest)
    if digit != expected:
        fail(422, "RUT inválido")
    return value


def local_actor(ctx, request, roles=None):
    return current_user(request, roles)


def account(db, id=None, username=None):
    """Datos de cuenta para Auth; las contraseñas nunca salen por APIs públicas."""
    row = db.execute(
        "SELECT u.*, c.email_verificado_at, c.activo AS cliente_activo FROM usuarios u LEFT JOIN clientes c ON c.id=u.cliente_id WHERE "
        + ("u.id=?" if id is not None else "u.identificador=? COLLATE NOCASE"),
        (id if id is not None else username,),
    ).fetchone()
    if not row:
        fail(404, "Cuenta no encontrada")
    data = dict(row)
    data["habilitado"] = bool(
        data["activo"]
        and (
            data["cliente_id"] is None
            or (data["cliente_activo"] and data["email_verificado_at"])
        )
    )
    data["version"] = digest(
        encode(
            {
                k: data[k]
                for k in (
                    "password_hash",
                    "identificador",
                    "rol",
                    "activo",
                    "email_verificado_at",
                    "cliente_activo",
                )
            }
        )
    )
    return data


PUBLIC_CLIENT = "id,nombres,apellidos,rut,email,telefono,direccion,comuna_id,comuna_nombre,provincia,region,fecha_nacimiento,sexo,email_verificado_at,activo"


def verification(ctx, db, client_id, email):
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.execute(
        "UPDATE clientes SET codigo_hash=?,codigo_expira_at=?,intentos_codigo=0,email_verificado_at=NULL WHERE id=?",
        (digest(code), later(900), client_id),
    )
    ctx.message(
        db,
        secrets.token_hex(16),
        email,
        "Verificación Fit Express (simulada)",
        f"cliente_id={client_id};codigo={code}",
    )


def create_app(ctx=None):
    ctx = ctx or Context("clients")
    app = application(ctx)

    async def commune(request, id):
        communes = await ctx.call("orders", "GET", "/comunas", request)
        found = next((x for x in communes if x["id"] == id), None)
        if not found:
            fail(422, "Comuna no habilitada")
        return found

    async def register(request, body, administrator=False):
        ctx.require_caller(request, "gateway")
        actor = (
            local_actor(ctx, request, {"administrador"})["id"]
            if administrator
            else "registro"
        )
        values = body.model_dump(mode="json")
        values["rut"] = rut_normalizado(body.rut)
        values["email"] = str(body.email).lower()
        cm = await commune(request, body.comuna_id)
        async with ctx.operation(request, "registro", actor, values) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                fields = list(values) + ["comuna_nombre", "created_at", "updated_at"]
                vals = list(values.values()) + [cm["nombre"], now(), now()]
                cur = db.execute(
                    f"INSERT INTO clientes({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                    vals,
                )
                id = cur.lastrowid
                db.execute(
                    "INSERT INTO usuarios(cliente_id,identificador,rol,created_at) VALUES(?,?,'cliente',?)",
                    (id, values["email"], now()),
                )
                verification(ctx, db, id, values["email"])
                op.save(
                    db,
                    {"cliente_id": id, "estado": "pendiente", "correo": "simulado"},
                    201,
                )
            return op.response()

    @app.post("/registro", status_code=201)
    async def registration(request: Request, body: Registro):
        return await register(request, body)

    @app.post("/admin/clientes", status_code=201)
    async def admin_registration(request: Request, body: Registro):
        return await register(request, body, True)

    @app.post("/clientes/verificar-correo")
    async def verify(request: Request, body: Verificar):
        ctx.require_caller(request, "gateway")
        # La contraseña no se conserva en el registro de idempotencia.
        async with ctx.operation(
            request,
            "verificacion",
            body.cliente_id,
            {
                "cliente_id": body.cliente_id,
                "codigo_hash": digest(body.codigo),
                "password_hash": private_fingerprint(ctx, body.password),
            },
        ) as op:
            if op.cached is not None:
                return op.response()
            bad = False
            with ctx.transaction() as db:
                client = db.execute(
                    "SELECT * FROM clientes WHERE id=?", (body.cliente_id,)
                ).fetchone()
                if not client or not client["codigo_hash"] or not client["activo"]:
                    fail(400, "Verificación no disponible")
                if client["intentos_codigo"] >= 5:
                    fail(429, "Código bloqueado; solicitar regeneración administrativa")
                if client["codigo_expira_at"] <= now():
                    fail(400, "Código vencido")
                if not secrets.compare_digest(
                    digest(body.codigo), client["codigo_hash"]
                ):
                    db.execute(
                        "UPDATE clientes SET intentos_codigo=intentos_codigo+1 WHERE id=?",
                        (body.cliente_id,),
                    )
                    bad = True
                else:
                    db.execute(
                        "UPDATE clientes SET email_verificado_at=?,codigo_hash=NULL,codigo_expira_at=NULL,updated_at=? WHERE id=?",
                        (now(), now(), body.cliente_id),
                    )
                    db.execute(
                        "UPDATE usuarios SET password_hash=? WHERE cliente_id=?",
                        (password_hash(body.password), body.cliente_id),
                    )
                    op.save(db, {"verificado": True})
            if bad:
                fail(400, "Código incorrecto")
            return op.response()

    @app.get("/perfil")
    async def profile(request: Request):
        ctx.require_caller(request, "graphql")
        u = local_actor(ctx, request)
        with ctx.read() as db:
            row = db.execute(
                f"SELECT {PUBLIC_CLIENT} FROM clientes WHERE id=?", (u["cliente_id"],)
            ).fetchone()
        return {
            "id": u["id"],
            "identificador": u["identificador"],
            "rol": u["rol"],
            "cliente_id": u["cliente_id"],
            "correo_verificado": bool(u["email_verificado_at"])
            if u["cliente_id"]
            else None,
            "perfil": {**dict(row), "comuna": row["comuna_nombre"]} if row else None,
        }

    @app.post("/interno/auth/credenciales")
    async def credentials(request: Request, body: Credenciales):
        ctx.require_caller(request, "auth")
        with ctx.read() as db:
            return account(db, username=body.username)

    @app.get("/interno/clientes/{id}")
    async def customer(id: int, request: Request):
        ctx.require_caller(request, "orders")
        with ctx.read() as db:
            row = db.execute(
                f"SELECT {PUBLIC_CLIENT} FROM clientes WHERE id=?", (id,)
            ).fetchone()
        if not row:
            fail(404, "No encontrado")
        return dict(row)

    @app.get("/interno/usuarios/{id}")
    async def user(id: int, request: Request):
        ctx.require_caller(request, "orders", "auth")
        with ctx.read() as db:
            data = account(db, id=id)
        if request.state.caller == "auth":
            return {
                k: data[k]
                for k in (
                    "id",
                    "identificador",
                    "rol",
                    "cliente_id",
                    "email_verificado_at",
                    "habilitado",
                    "version",
                )
            }
        return {k: data[k] for k in ("id", "identificador", "rol", "activo")}

    @app.get("/admin/clientes")
    async def customers(request: Request, pagina: int = 1, limite: int = 20):
        ctx.require_caller(request, "gateway")
        local_actor(ctx, request, {"administrador"})
        offset = pagination(pagina, limite)
        with ctx.read() as db:
            total = db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            rows = db.execute(
                f"SELECT {PUBLIC_CLIENT} FROM clientes ORDER BY id LIMIT ? OFFSET ?",
                (limite, offset),
            ).fetchall()
        return page([dict(x) for x in rows], total, pagina, limite)

    @app.patch("/admin/clientes/{id}")
    async def edit_customer(id: int, request: Request, body: ClientePatch):
        ctx.require_caller(request, "gateway")
        actor = local_actor(ctx, request, {"administrador"})
        changes = body.model_dump(mode="json", exclude_none=True)
        if "rut" in changes:
            changes["rut"] = rut_normalizado(changes["rut"])
        if "email" in changes:
            changes["email"] = changes["email"].lower()
        if "comuna_id" in changes:
            changes["comuna_nombre"] = (await commune(request, changes["comuna_id"]))[
                "nombre"
            ]
        async with ctx.operation(request, f"cliente:{id}", actor["id"], changes) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                row = db.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
                if not row:
                    fail(404, "No encontrado")
                email_changed = "email" in changes and changes["email"] != row["email"]
                if changes:
                    db.execute(
                        "UPDATE clientes SET "
                        + ",".join(f"{k}=?" for k in changes)
                        + ",updated_at=? WHERE id=?",
                        (*changes.values(), now(), id),
                    )
                if email_changed:
                    db.execute(
                        "UPDATE usuarios SET identificador=? WHERE cliente_id=?",
                        (changes["email"], id),
                    )
                if "activo" in changes:
                    db.execute(
                        "UPDATE usuarios SET activo=? WHERE cliente_id=?",
                        (changes["activo"], id),
                    )
                if email_changed or (
                    not row["email_verificado_at"]
                    and any(k != "activo" for k in changes)
                ):
                    verification(ctx, db, id, changes.get("email", row["email"]))
                result = dict(
                    db.execute(
                        f"SELECT {PUBLIC_CLIENT} FROM clientes WHERE id=?", (id,)
                    ).fetchone()
                )
                op.save(db, result)
            return op.response()

    @app.get("/admin/usuarios")
    async def users(request: Request, pagina: int = 1, limite: int = 20):
        ctx.require_caller(request, "gateway")
        local_actor(ctx, request, {"administrador"})
        offset = pagination(pagina, limite)
        with ctx.read() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol!='cliente'"
            ).fetchone()[0]
            rows = db.execute(
                "SELECT id,identificador,rol,activo FROM usuarios WHERE rol!='cliente' ORDER BY id LIMIT ? OFFSET ?",
                (limite, offset),
            ).fetchall()
        return page([dict(r) for r in rows], total, pagina, limite)

    @app.post("/admin/usuarios", status_code=201)
    async def create_staff(request: Request, body: Funcionario):
        ctx.require_caller(request, "gateway")
        actor = local_actor(ctx, request, {"administrador"})
        values = body.model_dump()
        values["password"] = private_fingerprint(ctx, body.password)
        async with ctx.operation(request, "funcionario", actor["id"], values) as op:
            if op.cached is not None:
                return op.response()
            with ctx.transaction() as db:
                cur = db.execute(
                    "INSERT INTO usuarios(identificador,password_hash,rol,created_at) VALUES(?,?,?,?)",
                    (
                        body.identificador.lower(),
                        password_hash(body.password),
                        body.rol,
                        now(),
                    ),
                )
                op.save(
                    db,
                    {
                        "id": cur.lastrowid,
                        "identificador": body.identificador.lower(),
                        "rol": body.rol,
                        "activo": 1,
                    },
                    201,
                )
            return op.response()

    @app.patch("/admin/usuarios/{id}")
    async def edit_staff(id: int, request: Request, body: FuncionarioPatch):
        ctx.require_caller(request, "gateway")
        actor = local_actor(ctx, request, {"administrador"})
        changes = body.model_dump(exclude_none=True)
        fingerprint = {
            **changes,
            **(
                {"password": private_fingerprint(ctx, changes["password"])}
                if "password" in changes
                else {}
            ),
        }
        async with ctx.operation(
            request, f"funcionario:{id}", actor["id"], fingerprint
        ) as op:
            if op.cached is not None:
                return op.response()
            if "password" in changes:
                changes["password_hash"] = password_hash(changes.pop("password"))
            if "identificador" in changes:
                changes["identificador"] = changes["identificador"].lower()
            with ctx.transaction() as db:
                if not db.execute(
                    "SELECT 1 FROM usuarios WHERE id=? AND rol!='cliente'", (id,)
                ).fetchone():
                    fail(404, "No encontrado")
                if changes:
                    db.execute(
                        "UPDATE usuarios SET "
                        + ",".join(f"{k}=?" for k in changes)
                        + " WHERE id=?",
                        (*changes.values(), id),
                    )
                op.save(
                    db,
                    dict(
                        db.execute(
                            "SELECT id,identificador,rol,activo FROM usuarios WHERE id=?",
                            (id,),
                        ).fetchone()
                    ),
                )
            return op.response()

    return app


app = create_app()
