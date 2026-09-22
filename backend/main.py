import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated, Literal

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
