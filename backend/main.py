import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from pydantic import BaseModel, Field

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import db


# === App ===
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
async def integridad(_: Request, exc: sqlite3.IntegrityError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


# === Modelos ===
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    precio: int = Field(ge=0)
    stock: int = Field(ge=0)
    categoria_id: int


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


@app.post("/productos", status_code=201)
def crear_producto(datos: ProductoIn, db: Db):
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
