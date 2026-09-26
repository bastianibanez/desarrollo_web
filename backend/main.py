import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, model_validator

import db

logger = logging.getLogger(__name__)


# === App ===
@asynccontextmanager
async def lifespan(_: FastAPI):
    db.inicializar()
    yield


app = FastAPI(title="FitExpress API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

Db = Annotated[sqlite3.Connection, Depends(db.get_db)]


@app.exception_handler(sqlite3.IntegrityError)
async def integridad(request: Request, exc: sqlite3.IntegrityError):
    # El mensaje de SQLite expone el esquema: se registra acá y al cliente va uno genérico
    logger.warning("IntegrityError en %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse({"detail": "Conflicto con datos existentes"}, status_code=409)


# === Modelos ===
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    precio: int = Field(ge=0)
    stock: int = Field(ge=0)
    categoria_id: int


class ClienteIn(BaseModel):
    nombres: str = Field(min_length=1)
    apellidos: str = Field(min_length=1)
    rut: str = Field(min_length=1)
    email: EmailStr
    telefono: str | None = None


class DireccionIn(BaseModel):
    calle: str = Field(min_length=1)
    numero: str = Field(min_length=1)
    departamento: str | None = None
    comuna_id: int


class ItemIn(BaseModel):
    producto_id: int | None = None
    combo_id: int | None = None
    cantidad: int = Field(ge=1)

    @model_validator(mode="after")
    def producto_xor_combo(self):
        if (self.producto_id is None) == (self.combo_id is None):
            raise ValueError("Cada item requiere producto_id o combo_id (no ambos)")
        return self


class OrdenIn(BaseModel):
    cliente: ClienteIn
    direccion: DireccionIn
    items: list[ItemIn] = Field(min_length=1)


# === Catalogo ===
@app.get("/categorias")
def listar_categorias(db: Db):
    return [dict(f) for f in db.execute("SELECT * FROM categorias ORDER BY nombre")]


@app.get("/productos")
def listar_productos(db: Db):
    filas = db.execute("""
        SELECT p.*, c.nombre AS categoria
        FROM productos p
        JOIN categorias c ON c.id = p.categoria_id
        ORDER BY p.nombre
    """)
    return [dict(f) for f in filas]


@app.get("/productos/{id}")
def obtener_producto(id: int, db: Db):
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


@app.post("/productos", status_code=201)
def crear_producto(datos: ProductoIn, db: Db):
    validar_categoria(db, datos.categoria_id)
    with db:
        cur = db.execute(
            "INSERT INTO productos (nombre, descripcion, precio, stock, categoria_id) VALUES (?, ?, ?, ?, ?)",
            (
                datos.nombre,
                datos.descripcion,
                datos.precio,
                datos.stock,
                datos.categoria_id,
            ),
        )
    return dict(
        db.execute("SELECT * FROM productos WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


@app.put("/productos/{id}")
def actualizar_producto(id: int, datos: ProductoIn, db: Db):
    validar_categoria(db, datos.categoria_id)
    with db:
        cur = db.execute(
            "UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, stock = ?, categoria_id = ? WHERE id = ?",
            (
                datos.nombre,
                datos.descripcion,
                datos.precio,
                datos.stock,
                datos.categoria_id,
                id,
            ),
        )
    if cur.rowcount == 0:
        raise HTTPException(404, "No encontrado")
    return dict(db.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone())


@app.delete("/productos/{id}")
def eliminar_producto(id: int, db: Db):
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


@app.post("/ordenes", status_code=201)
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


@app.get("/ordenes/{id}")
def obtener_orden(id: int, db: Db):
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
    if fila is None:
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
