import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import db
from modelos import (
    ClienteEdicionIn,
    ClienteRegistroIn,
    LoginIn,
    OrdenIn,
    ProductoIn,
    UsuarioEdicionIn,
    UsuarioIn,
    VerificarCorreoIn,
)
from seguridad import (
    crear_sesion,
    hash_password,
    password_valida,
    requiere,
    usuario_actual,
)
from correo import enviar_correo

logger = logging.getLogger(__name__)

INTERNAL_GATEWAY_SECRET = os.getenv("INTERNAL_GATEWAY_SECRET", None)

if INTERNAL_GATEWAY_SECRET is None:
    raise RuntimeError("INTERNAL_GATEWAY_SECRET no configurado")


def verify_gateway(x_gateway_secret: str = Header(default="")):
    valid = secrets.compare_digest(x_gateway_secret, INTERNAL_GATEWAY_SECRET)

    if not valid:
        raise HTTPException(
            status_code=403, detail="Solicitud no autorizada desde Gateway"
        )


# === App ===
@asynccontextmanager
async def lifespan(_: FastAPI):
    db.inicializar()
    yield


app = FastAPI(title="FitExpress Protected Backend API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

Db = Annotated[sqlite3.Connection, Depends(db.get_db)]


MAX_INTENTOS_CODIGO = 5


def nuevo_codigo() -> tuple[str, str, str]:
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    digest = hashlib.sha256(codigo.encode()).hexdigest()
    expira = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    return codigo, digest, expira


def validar_digito_rut(rut: str) -> None:
    cuerpo, guion, digito = rut.rpartition("-")
    if (
        not guion
        or not cuerpo.isdecimal()
        or len(cuerpo) > 8
        or len(digito) != 1
        or digito not in "0123456789K"
    ):
        raise HTTPException(422, "RUT inválido")
    suma = sum(int(n) * (2 + i % 6) for i, n in enumerate(reversed(cuerpo)))
    resto = 11 - suma % 11
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    if digito != esperado:
        raise HTTPException(422, "RUT inválido")


def registrar_cliente(datos: ClienteRegistroIn, db: Db):
    rut = normalizar_rut(datos.rut)
    validar_digito_rut(rut)  # implementar con el algoritmo de frontend/src/rut.js
    codigo, digest, expira = nuevo_codigo()
    email = str(datos.email).lower()
    if (
        db.execute("SELECT 1 FROM comunas WHERE id = ?", (datos.comuna_id,)).fetchone()
        is None
    ):
        raise HTTPException(400, "Comuna no existe")
    with db:
        cur = db.execute(
            """
            INSERT INTO clientes
            (nombres, apellidos, rut, email, telefono, direccion,
             comuna_id, provincia, region, fecha_nacimiento, sexo,
             codigo_hash, codigo_expira_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                datos.nombres,
                datos.apellidos,
                rut,
                email,
                datos.telefono,
                datos.direccion,
                datos.comuna_id,
                datos.provincia,
                datos.region,
                datos.fecha_nacimiento.isoformat(),
                datos.sexo,
                digest,
                expira,
            ),
        )
        cliente_id = cur.lastrowid
        db.execute(
            """
            INSERT INTO usuarios (cliente_id, identificador, rol)
            VALUES (?, ?, 'cliente')
        """,
            (cliente_id, email),
        )
    enviar_enlace_confirmacion(email, cliente_id, codigo)
    return {"cliente_id": cliente_id, "estado": "pendiente"}


def enviar_enlace_confirmacion(email: str, cliente_id: int, codigo: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    enlace = f"{frontend_url}/confirmar.html?cliente={cliente_id}&codigo={codigo}"
    enviar_correo(
        email,
        "Confirma tu cuenta FitExpress",
        f"Confirma tu correo y elige tu contraseña aquí: {enlace}",
    )


@app.exception_handler(sqlite3.IntegrityError)
async def integridad(request: Request, exc: sqlite3.IntegrityError):
    # El mensaje de SQLite expone el esquema: se registra acá y al cliente va uno genérico
    logger.warning("IntegrityError en %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse({"detail": "Conflicto con datos existentes"}, status_code=409)


# === Catalogo ===
@app.get("/categorias")
def listar_categorias(db: Db):
    return [dict(f) for f in db.execute("SELECT * FROM categorias ORDER BY nombre")]


@app.get("/productos", dependencies=[Depends(verify_gateway)])
def listar_productos(db: Db):
    filas = db.execute("""
        SELECT p.*, c.nombre AS categoria
        FROM productos p
        JOIN categorias c ON c.id = p.categoria_id
        ORDER BY p.nombre
    """)
    return [dict(f) for f in filas]


@app.get("/productos/{id}")
def obtener_producto(
    id: int,
    db: Db,
):
    fila = db.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone()
    if fila is None:
        raise HTTPException(404, "No encontrado")
    return dict(fila)


def validar_categoria(db: sqlite3.Connection, categoria_id: int) -> None:
    if (
        db.execute("SELECT 1 FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
        is None
    ):
        raise HTTPException(400, "Categoría no existe")


@app.post("/productos", status_code=201, dependencies=[Depends(verify_gateway)])
def crear_producto(
    datos: ProductoIn, db: Db, _=Depends(requiere("administrador", "dueno"))
):
    validar_categoria(db, datos.categoria_id)
    with db:
        cur = db.execute(
            "INSERT INTO productos (nombre, descripcion, precio, precio_oferta, stock, categoria_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                datos.nombre,
                datos.descripcion,
                datos.precio,
                datos.precio_oferta,
                datos.stock,
                datos.categoria_id,
            ),
        )
    return dict(
        db.execute("SELECT * FROM productos WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


@app.put("/productos/{id}", dependencies=[Depends(verify_gateway)])
def actualizar_producto(
    id: int, datos: ProductoIn, db: Db, _=Depends(requiere("administrador", "dueno"))
):
    validar_categoria(db, datos.categoria_id)
    with db:
        cur = db.execute(
            "UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, precio_oferta = ?, stock = ?, categoria_id = ? WHERE id = ?",
            (
                datos.nombre,
                datos.descripcion,
                datos.precio,
                datos.precio_oferta,
                datos.stock,
                datos.categoria_id,
                id,
            ),
        )
    if cur.rowcount == 0:
        raise HTTPException(404, "No encontrado")
    return dict(db.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone())


@app.delete("/productos/{id}", dependencies=[Depends(verify_gateway)])
def eliminar_producto(id: int, db: Db, _=Depends(requiere("administrador", "dueno"))):
    with db:
        cur = db.execute("DELETE FROM productos WHERE id = ?", (id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "No encontrado")
    return {"ok": True}


@app.get("/combos")
def listar_combos(db: Db):
    resultado = []
    for fila in db.execute("SELECT * FROM combos ORDER BY nombre"):
        combo = dict(fila)
        combo["productos"] = [
            dict(p)
            for p in db.execute(
                """
                SELECT p.id, p.nombre, lc.cantidad
                FROM lineas_combo lc
                JOIN productos p ON p.id = lc.producto_id
                WHERE lc.combo_id = ?
            """,
                (combo["id"],),
            )
        ]

        componentes = db.execute(
            """
            SELECT lc.cantidad, p.stock
            FROM lineas_combo lc
            JOIN productos p ON p.id = lc.producto_id
        """,
            (combo["id"],),
        ).fetchall()

        combo["disponible"] = bool(componentes) and all(
            f["stock"] >= f["cantidad"] for f in componentes
        )
        resultado.append(combo)
    return resultado


# === Comunas ===
@app.get("/comunas")
def listar_comunas(db: Db):
    return [
        dict(f)
        for f in db.execute("""
        SELECT c.id, c.nombre, c.ciudad, c.region, e.costo AS costo_envio
        FROM comunas c
        JOIN costos_envio e ON e.comuna_id = c.id
        ORDER BY c.nombre
    """)
    ]


# === Ordenes ===


def normalizar_rut(rut: str) -> str:
    return rut.replace(".", "").upper()


@app.post("/ordenes", status_code=201, dependencies=[Depends(verify_gateway)])
def crear_orden(orden: OrdenIn, db: Db):
    envio = db.execute(
        "SELECT costo FROM costos_envio WHERE comuna_id = ?",
        (orden.direccion.comuna_id,),
    ).fetchone()
    if envio is None:
        raise HTTPException(400, "No hay despacho a esa comuna")

    lineas = []
    for item in orden.items:
        if item.producto_id is not None:
            fila = db.execute(
                "SELECT precio FROM productos WHERE id = ?", (item.producto_id,)
            ).fetchone()
            if fila is None:
                raise HTTPException(400, "Producto no existe")
        else:
            fila = db.execute(
                "SELECT precio FROM combos WHERE id = ?", (item.combo_id,)
            ).fetchone()
            if fila is None:
                raise HTTPException(400, "Combo no existe")
        lineas.append((item.producto_id, item.combo_id, item.cantidad, fila["precio"]))

    subtotal = sum(cantidad * precio for _, _, cantidad, precio in lineas)
    costo_envio = envio["costo"]
    total = subtotal + costo_envio
    rut = normalizar_rut(orden.cliente.rut)

    with db:
        existente = db.execute(
            "SELECT id FROM clientes WHERE rut = ?", (rut,)
        ).fetchone()
        if existente is None:
            c = orden.cliente
            cur = db.execute(
                "INSERT INTO clientes (nombres, apellidos, rut, email, telefono) VALUES (?,?,?,?,?)",
                (c.nombres, c.apellidos, rut, c.email, c.telefono),
            )
            cliente_id = cur.lastrowid
        else:
            cliente_id = existente["id"]

        d = orden.direccion
        cur = db.execute(
            "INSERT INTO ordenes (cliente_id, calle, numero, departamento, comuna_id, subtotal, costo_envio, total) VALUES (?,?,?,?,?,?,?,?)",
            (
                cliente_id,
                d.calle,
                d.numero,
                d.departamento,
                d.comuna_id,
                subtotal,
                costo_envio,
                total,
            ),
        )
        orden_id = cur.lastrowid

        db.executemany(
            "INSERT INTO lineas_orden (orden_id, producto_id, combo_id, cantidad, precio_unitario) VALUES (?,?,?,?,?)",
            [(orden_id, pid, cid, cant, precio) for pid, cid, cant, precio in lineas],
        )
    return {
        "id": orden_id,
        "subtotal": subtotal,
        "costo_envio": costo_envio,
        "total": total,
    }


@app.get("/ordenes/{id}", dependencies=[Depends(verify_gateway)])
def obtener_orden(id: int, db: Db, usuario=Depends(usuario_actual)):
    fila = db.execute(
        """
        SELECT o.*, cl.nombres, cl.apellidos, cl.rut, cl.email, cl.telefono, cm.nombre AS comuna
        FROM ordenes o
        JOIN clientes cl ON cl.id = o.cliente_id 
        JOIN comunas cm ON cm.id = o.comuna_id
        WHERE o.id = ?
        """,
        (id,),
    ).fetchone()
    # Un cliente solo ve sus órdenes; el resto de los perfiles ve cualquiera
    if fila is None or (
        usuario["rol"] == "cliente" and fila["cliente_id"] != usuario["cliente_id"]
    ):
        raise HTTPException(404, "No encontrado")

    orden = dict(fila)
    orden["lineas"] = [
        dict(l)
        for l in db.execute(
            """
            SELECT producto_id, combo_id, cantidad, precio_unitario
            FROM lineas_orden
            WHERE orden_id = ?
            """,
            (id,),
        )
    ]
    return orden


@app.post("/clientes/verificar-correo")
def verificar_correo(datos: VerificarCorreoIn, db: Db):
    cliente = db.execute(
        "SELECT * FROM clientes WHERE id = ?", (datos.cliente_id,)
    ).fetchone()
    if cliente is None or cliente["codigo_hash"] is None:
        raise HTTPException(400, "Verificación no disponible")
    if cliente["codigo_expira_at"] <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(400, "Código vencido")
    if cliente["intentos_codigo"] >= MAX_INTENTOS_CODIGO:
        raise HTTPException(
            429, "Demasiados intentos: pide al administrador un código nuevo"
        )
    digest = hashlib.sha256(datos.codigo.encode()).hexdigest()
    if not secrets.compare_digest(digest, cliente["codigo_hash"]):
        with db:
            db.execute(
                "UPDATE clientes SET intentos_codigo = intentos_codigo + 1 WHERE id = ?",
                (datos.cliente_id,),
            )
        raise HTTPException(400, "Código incorrecto")
    with db:
        db.execute(
            """
            UPDATE clientes SET email_verificado_at = ?,
                codigo_hash = NULL, codigo_expira_at = NULL WHERE id = ?
        """,
            (datetime.now(timezone.utc).isoformat(), datos.cliente_id),
        )
        db.execute(
            "UPDATE usuarios SET password_hash = ? WHERE cliente_id = ?",
            (hash_password(datos.password), datos.cliente_id),
        )
    return {"verificado": True}


@app.post("/registro", status_code=201)
def registro_web(datos: ClienteRegistroIn, db: Db):
    return registrar_cliente(datos, db)


@app.post("/admin/clientes", status_code=201)
def registro_admin(
    datos: ClienteRegistroIn, db: Db, _=Depends(requiere("administrador"))
):
    return registrar_cliente(datos, db)


@app.post("/login")
def login(datos: LoginIn, db: Db):
    usuario = db.execute(
        """
        SELECT u.*, c.email_verificado_at FROM usuarios u
        LEFT JOIN clientes c ON c.id = u.cliente_id
        WHERE u.identificador = ? AND u.activo = 1
    """,
        (datos.identificador.lower(),),
    ).fetchone()
    if usuario is None or not password_valida(datos.password, usuario["password_hash"]):
        raise HTTPException(401, "Credenciales inválidas")
    if usuario["rol"] == "cliente" and not usuario["email_verificado_at"]:
        raise HTTPException(403, "Correo sin verificar")
    return {"sesion": crear_sesion(db, usuario["id"]), "rol": usuario["rol"]}


@app.post("/logout")
def logout(
    db: Db,
    _=Depends(usuario_actual),
    x_user_session: str = Header(default=""),
):
    token_hash = hashlib.sha256(x_user_session.encode()).hexdigest()
    with db:
        db.execute("DELETE FROM sesiones WHERE token_hash = ?", (token_hash,))
    return {"ok": True}


@app.get("/yo")
def yo(db: Db, usuario=Depends(usuario_actual)):
    datos = {
        "id": usuario["id"],
        "identificador": usuario["identificador"],
        "rol": usuario["rol"],
        "cliente_id": usuario["cliente_id"],
    }
    if usuario["cliente_id"] is not None:
        perfil = db.execute(
            """
            SELECT c.nombres, c.apellidos, c.rut, c.email, c.telefono,
                   c.direccion, cm.nombre AS comuna
            FROM clientes c LEFT JOIN comunas cm ON cm.id = c.comuna_id
            WHERE c.id = ?
        """,
            (usuario["cliente_id"],),
        ).fetchone()
        datos["perfil"] = dict(perfil)
    return datos


# === Mantenedor de clientes (administrador) ===
COLUMNAS_CLIENTE = """id, nombres, apellidos, rut, email, telefono, direccion,
    comuna_id, provincia, region, fecha_nacimiento, sexo,
    email_verificado_at, activo"""


@app.get("/admin/clientes")
def listar_clientes(db: Db, _=Depends(requiere("administrador"))):
    return [
        dict(f)
        for f in db.execute(f"SELECT {COLUMNAS_CLIENTE} FROM clientes ORDER BY id")
    ]


@app.patch("/admin/clientes/{id}")
def editar_cliente(
    id: int,
    datos: ClienteEdicionIn,
    db: Db,
    _=Depends(requiere("administrador")),
):
    cliente = db.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
    if cliente is None:
        raise HTTPException(404, "No encontrado")

    cambios = datos.model_dump(exclude_none=True)
    if "rut" in cambios:
        cambios["rut"] = normalizar_rut(cambios["rut"])
        validar_digito_rut(cambios["rut"])
    if "email" in cambios:
        cambios["email"] = str(cambios["email"]).lower()
        if cambios["email"] == cliente["email"]:
            del cambios["email"]  # el formulario reenvía el correo sin cambios
    if "fecha_nacimiento" in cambios:
        cambios["fecha_nacimiento"] = cambios["fecha_nacimiento"].isoformat()
    if "activo" in cambios:
        cambios["activo"] = int(cambios["activo"])
    if (
        "comuna_id" in cambios
        and db.execute(
            "SELECT 1 FROM comunas WHERE id = ?", (cambios["comuna_id"],)
        ).fetchone()
        is None
    ):
        raise HTTPException(400, "Comuna no existe")

    # Un correo nuevo, o editar una cuenta aún pendiente, genera un código nuevo
    # y un enlace nuevo (así el administrador desbloquea a quien agotó los intentos)
    pendiente = cliente["email_verificado_at"] is None
    regenerar = "email" in cambios or (
        pendiente and any(campo != "activo" for campo in cambios)
    )
    with db:
        if cambios:
            asignaciones = ", ".join(f"{campo} = ?" for campo in cambios)
            db.execute(
                f"UPDATE clientes SET {asignaciones} WHERE id = ?",
                (*cambios.values(), id),
            )
        if "email" in cambios:
            db.execute(
                "UPDATE clientes SET email_verificado_at = NULL WHERE id = ?", (id,)
            )
            db.execute(
                "UPDATE usuarios SET identificador = ? WHERE cliente_id = ?",
                (cambios["email"], id),
            )
        if "activo" in cambios:
            db.execute(
                "UPDATE usuarios SET activo = ? WHERE cliente_id = ?",
                (cambios["activo"], id),
            )
        if regenerar:
            codigo, digest, expira = nuevo_codigo()
            db.execute(
                "UPDATE clientes SET codigo_hash = ?, codigo_expira_at = ?, intentos_codigo = 0 WHERE id = ?",
                (digest, expira, id),
            )
    if regenerar:
        enviar_enlace_confirmacion(cambios.get("email", cliente["email"]), id, codigo)
    return dict(
        db.execute(
            f"SELECT {COLUMNAS_CLIENTE} FROM clientes WHERE id = ?", (id,)
        ).fetchone()
    )


# === Mantenedor de usuarios / funcionarios (administrador) ===
@app.get("/admin/usuarios")
def listar_usuarios(db: Db, _=Depends(requiere("administrador"))):
    return [
        dict(f)
        for f in db.execute(
            "SELECT id, identificador, rol, activo FROM usuarios WHERE rol != 'cliente' ORDER BY id"
        )
    ]


@app.post("/admin/usuarios", status_code=201)
def crear_usuario(datos: UsuarioIn, db: Db, _=Depends(requiere("administrador"))):
    identificador = datos.identificador.strip().lower()
    with db:
        cur = db.execute(
            "INSERT INTO usuarios (identificador, password_hash, rol) VALUES (?, ?, ?)",
            (identificador, hash_password(datos.password), datos.rol),
        )
    return {
        "id": cur.lastrowid,
        "identificador": identificador,
        "rol": datos.rol,
        "activo": 1,
    }


@app.patch("/admin/usuarios/{id}")
def editar_usuario(
    id: int,
    datos: UsuarioEdicionIn,
    db: Db,
    _=Depends(requiere("administrador")),
):
    fila = db.execute(
        "SELECT 1 FROM usuarios WHERE id = ? AND rol != 'cliente'", (id,)
    ).fetchone()
    if fila is None:
        raise HTTPException(404, "No encontrado")

    cambios = datos.model_dump(exclude_none=True)
    if "identificador" in cambios:
        cambios["identificador"] = cambios["identificador"].strip().lower()
    if "password" in cambios:
        cambios["password_hash"] = hash_password(cambios.pop("password"))
    if "activo" in cambios:
        cambios["activo"] = int(cambios["activo"])
    if cambios:
        asignaciones = ", ".join(f"{campo} = ?" for campo in cambios)
        with db:
            db.execute(
                f"UPDATE usuarios SET {asignaciones} WHERE id = ?",
                (*cambios.values(), id),
            )
    return dict(
        db.execute(
            "SELECT id, identificador, rol, activo FROM usuarios WHERE id = ?", (id,)
        ).fetchone()
    )
