"""Infraestructura compartida; cada proceso conserva su propia base e identidad."""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("fitexpress")
ROLES = {"cliente", "administrador", "cajero", "despacho", "dueno"}
ORDER_STATES = {
    "pendiente",
    "pagado",
    "preparando",
    "enviado",
    "entregado",
    "cancelado",
    "expirado",
}
MAX_MONEY = 2_147_483_647


def now():
    return datetime.now(UTC).isoformat()


def later(seconds):
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def private_fingerprint(ctx, value):
    """Idempotencia de contraseñas sin un verificador rápido recuperable desde SQLite."""
    return hmac.new(
        ctx.keys["incoming"]["gateway"].encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fail(status, message, code=None):
    raise HTTPException(status, {"detail": message, "codigo": code or f"HTTP_{status}"})


def money(value):
    if type(value) is not int or not 0 <= value <= MAX_MONEY:
        fail(422, "Importe fuera de rango")
    return value


def pagination(pagina=1, limite=20):
    if not 1 <= pagina <= 1_000_000 or not 1 <= limite <= 50:
        fail(422, "Paginación inválida")
    return (pagina - 1) * limite


def page(items, total, pagina, limite):
    return {
        "items": items,
        "paginacion": {"pagina": pagina, "limite": limite, "total": total},
    }


def period(desde, hasta):
    try:
        start, end = date.fromisoformat(desde), date.fromisoformat(hasta)
        if start > end:
            raise ValueError()
        zone = ZoneInfo("America/Santiago")
        a = datetime.combine(start, datetime.min.time(), zone).astimezone(UTC)
        b = datetime.combine(
            end + timedelta(days=1), datetime.min.time(), zone
        ).astimezone(UTC)
        return a.isoformat(), b.isoformat()
    except (ValueError, TypeError, OverflowError):
        fail(422, "Rango de fechas inválido")


def password_hash(password):
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${value.hex()}"


def password_matches(password, saved):
    try:
        _, iterations, salt, expected = saved.split("$")
        value = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(value.hex(), expected)
    except (AttributeError, ValueError, TypeError):
        return False


TECH_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operaciones(
 id TEXT PRIMARY KEY, actor TEXT NOT NULL, tipo TEXT NOT NULL, clave TEXT NOT NULL,
 solicitud_hash TEXT NOT NULL, datos TEXT NOT NULL DEFAULT '{}', resultado TEXT,
 status INTEGER, creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL,
 UNIQUE(actor,tipo,clave));
CREATE TABLE IF NOT EXISTS mensajes_simulados(
 id TEXT PRIMARY KEY, destinatario TEXT NOT NULL, asunto TEXT NOT NULL,
 cuerpo TEXT NOT NULL, estado TEXT NOT NULL CHECK(estado='simulado'), creado_en TEXT NOT NULL);
"""


def identity_headers(user):
    """Solo se envía por tramos internos autenticados; nunca se copia del navegador."""
    if not user:
        return {}
    return {
        "X-Authenticated-User-ID": str(user["id"]),
        "X-Authenticated-User": user["identificador"],
        "X-Authenticated-Roles": user["rol"],
        "X-Authenticated-Client-ID": str(user["cliente_id"] or ""),
        "X-Authenticated-Email-Verified": "1"
        if user.get("email_verificado_at")
        else "0",
    }


def read_identity(headers):
    if not headers.get("x-authenticated-user-id"):
        return None
    try:
        role = headers["x-authenticated-roles"]
        if role not in ROLES:
            raise ValueError()
        return {
            "id": int(headers["x-authenticated-user-id"]),
            "identificador": headers["x-authenticated-user"],
            "rol": role,
            "cliente_id": int(headers["x-authenticated-client-id"])
            if headers.get("x-authenticated-client-id")
            else None,
            "email_verificado_at": headers.get("x-authenticated-email-verified") == "1",
        }
    except (ValueError, KeyError):
        fail(401, "Contexto de identidad inválido")


def current_user(request, roles=None, optional=False):
    user = getattr(request.state, "user", None)
    if not user:
        if optional:
            return None
        fail(401, "Sesión requerida o vencida")
    if roles and user["rol"] not in roles:
        fail(403, "Perfil sin permiso")
    return user


class Context:
    def __init__(self, name, data_dir=None, credentials=None, transport=None):
        self.name = name
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "var/backend"))
        self.path = self.data_dir / f"{name}.db"
        self.keys = credentials
        self.transport = transport
        self.locks = {}
        self.http = None
        self.tasks = []

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @contextmanager
    def read(self):
        db = self.connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.read() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def initialize(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.read() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(TECH_SCHEMA)
            schema = Path(__file__).parent / self.name / "schema.sql"
            if schema.exists():
                db.executescript(schema.read_text())
            db.execute("INSERT OR IGNORE INTO schema_migrations VALUES(1,?)", (now(),))

    async def load_keys(self):
        """Carga la identidad una vez; para cambiarla se reinicia el servicio."""
        if self.keys is not None:
            return
        token_file = Path(os.getenv("VAULT_TOKEN_FILE", "/run/identity/token"))
        try:
            token = token_file.read_text().strip()
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(
                    os.getenv("VAULT_ADDR", "http://vault:8200")
                    + f"/v1/secret/data/services/{self.name}",
                    headers={"X-Vault-Token": token},
                )
                r.raise_for_status()
                self.keys = r.json()["data"]["data"]
        except (OSError, httpx.HTTPError, KeyError, ValueError):
            fail(503, "Identidad de servicio no disponible", "VAULT_UNAVAILABLE")

    def url(self, target):
        if target == "auth":
            return os.getenv("AUTH_SERVICE_URL", "http://auth:8100")
        return os.getenv(f"{target.upper()}_URL", f"http://{target}:9000")

    async def call(
        self,
        target,
        method,
        path,
        request=None,
        body=None,
        params=None,
        key=None,
        headers=None,
    ):
        await self.load_keys()
        token = self.keys.get("outgoing", {}).get(target)
        if not token:
            fail(403, "Integración no autorizada")
        outgoing = {
            "X-Gateway-Secret": token,
            "X-Request-ID": str(uuid.uuid4()),
        }
        if target == "auth":
            outgoing["X-Gateway-Auth-Secret"] = token
        if request:
            outgoing["X-Request-ID"] = getattr(
                request.state, "request_id", outgoing["X-Request-ID"]
            )
            outgoing.update(identity_headers(getattr(request.state, "user", None)))
        if key:
            outgoing["Idempotency-Key"] = key
        outgoing.update(headers or {})
        try:
            r = await self.http.request(
                method,
                self.url(target) + path,
                json=body,
                params=params,
                headers=outgoing,
                timeout=3,
            )
        except httpx.RequestError:
            fail(503, "Servicio dependiente no disponible", "DEPENDENCY_UNAVAILABLE")
        if r.status_code >= 400:
            try:
                payload = r.json()
                detail = payload.get("detail", "Operación rechazada")
                if isinstance(detail, dict):
                    detail = detail.get("detail", "Operación rechazada")
            except ValueError:
                detail = "Servicio dependiente no disponible"
            fail(
                r.status_code if r.status_code < 500 else 503,
                detail,
                "DEPENDENCY_UNAVAILABLE" if r.status_code >= 500 else None,
            )
        try:
            return r.json()
        except ValueError:
            fail(503, "Respuesta dependiente inválida", "DEPENDENCY_UNAVAILABLE")

    async def actor(self, request, roles=None, optional=False):
        return current_user(request, roles, optional)

    def require_caller(self, request, *callers):
        if request.state.caller not in callers:
            fail(403, "Identidad técnica sin permiso")

    @asynccontextmanager
    async def operation(self, request, kind, actor, payload):
        key = request.headers.get("idempotency-key", "")
        if not 1 <= len(key) <= 128 or any(ord(c) < 32 for c in key):
            fail(422, "Idempotency-Key requerida (1–128 caracteres)")
        actor_ref = str(actor)
        identity = digest(f"{actor_ref}:{kind}:{key}")
        lock = self.locks.setdefault(identity, asyncio.Lock())
        async with lock:
            fingerprint = digest(encode(payload))
            with self.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO operaciones(id,actor,tipo,clave,solicitud_hash,creado_en,actualizado_en) VALUES(?,?,?,?,?,?,?)",
                    (identity, actor_ref, kind, key, fingerprint, now(), now()),
                )
                row = dict(
                    db.execute(
                        "SELECT * FROM operaciones WHERE id=?", (identity,)
                    ).fetchone()
                )
                if row["solicitud_hash"] != fingerprint:
                    fail(
                        409,
                        "Clave reutilizada con otro contenido",
                        "IDEMPOTENCY_CONFLICT",
                    )
            yield Operation(self, row)

    def message(self, db, id, email, subject, body):
        db.execute(
            "INSERT OR IGNORE INTO mensajes_simulados VALUES(?,?,?,?,?,?)",
            (id, email, subject, body, "simulado", now()),
        )


class Operation:
    def __init__(self, ctx, row):
        self.ctx, self.id = ctx, row["id"]
        self.data = json.loads(row["datos"])
        self.cached = json.loads(row["resultado"]) if row["resultado"] else None
        self.status = row["status"] or 200

    def response(self):
        return JSONResponse(self.cached, status_code=self.status)

    def save(self, db, result=None, status=200, **data):
        self.data.update(data)
        db.execute(
            "UPDATE operaciones SET datos=?,resultado=?,status=?,actualizado_en=? WHERE id=?",
            (
                encode(self.data),
                encode(result) if result is not None else None,
                status,
                now(),
                self.id,
            ),
        )
        self.cached, self.status = result, status


def application(ctx, startup=None, worker=None, external=False):
    @asynccontextmanager
    async def lifespan(app):
        await ctx.load_keys()
        ctx.initialize()
        ctx.http = httpx.AsyncClient(transport=ctx.transport, timeout=3)
        if startup:
            startup(ctx)
        if worker and not getattr(ctx, "disable_workers", False):
            ctx.tasks.append(asyncio.create_task(worker(ctx)))
        yield
        for task in ctx.tasks:
            task.cancel()
        await asyncio.gather(*ctx.tasks, return_exceptions=True)
        await ctx.http.aclose()

    app = FastAPI(title=f"Fit Express · {ctx.name}", version="2.0.0", lifespan=lifespan)
    app.state.ctx = ctx

    @app.middleware("http")
    async def protect(request, next_call):
        correlation = request.headers.get("x-request-id", "")
        request.state.request_id = (
            correlation
            if 1 <= len(correlation) <= 100
            and correlation.isascii()
            and correlation.isprintable()
            else str(uuid.uuid4())
        )
        try:
            if request.url.path not in {"/health"}:
                if int(request.headers.get("content-length", "0")) > 65536:
                    fail(413, "Cuerpo demasiado grande")
                if len(await request.body()) > 65536:
                    fail(413, "Cuerpo demasiado grande")
                if not external:
                    await ctx.load_keys()
                    token = request.headers.get("x-gateway-secret", "")
                    caller = next(
                        (
                            n
                            for n, k in ctx.keys.get("incoming", {}).items()
                            if hmac.compare_digest(token, k)
                        ),
                        None,
                    )
                    if not caller:
                        fail(403, "Identidad técnica requerida")
                    request.state.caller = caller
                    request.state.user = read_identity(request.headers)
            response = await next_call(request)
        except HTTPException as exc:
            response = error_response(request, exc.status_code, exc.detail, exc.headers)
        except Exception as exc:  # noqa: BLE001 -- frontera HTTP: no exponer excepciones ni datos privados
            log.error(
                "%s request_id=%s error=%s",
                ctx.name,
                request.state.request_id,
                type(exc).__name__,
            )
            response = error_response(
                request, 500, "No fue posible completar la operación"
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    def error_response(request, status, detail, headers=None):
        payload = (
            detail
            if isinstance(detail, dict)
            else {"detail": detail, "codigo": f"HTTP_{status}"}
        )
        return JSONResponse(
            {**payload, "request_id": getattr(request.state, "request_id", "")},
            status_code=status,
            headers=headers,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, exc.detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(
            request,
            422,
            {
                "detail": "Entrada inválida",
                "codigo": "VALIDATION_ERROR",
                "campos": [".".join(map(str, e["loc"])) for e in exc.errors()],
            },
        )

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return error_response(request, 409, "Conflicto con datos existentes")

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return error_response(request, 503, "Persistencia temporalmente no disponible")

    @app.get("/health")
    async def health():
        with ctx.read() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "service": ctx.name}

    return app
