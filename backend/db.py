import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# === Esquema ===

SCHEMA = """
CREATE TABLE IF NOT EXISTS categorias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS productos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  precio INTEGER NOT NULL CHECK (precio >= 0),
  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  categoria_id INTEGER NOT NULL REFERENCES categorias(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS combos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  precio INTEGER NOT NULL CHECK (precio >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lineas_combo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  combo_id INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad INTEGER NOT NULL DEFAULT 1 CHECK (cantidad > 0),
  UNIQUE (combo_id, producto_id)
);

CREATE TABLE IF NOT EXISTS comunas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  ciudad TEXT NOT NULL,
  region TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS costos_envio (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  comuna_id INTEGER NOT NULL UNIQUE REFERENCES comunas(id),
  costo INTEGER NOT NULL CHECK (costo >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombres TEXT NOT NULL,
  apellidos TEXT NOT NULL,
  rut TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  telefono TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ordenes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id),
  calle TEXT NOT NULL,
  numero TEXT NOT NULL,
  departamento TEXT,
  comuna_id INTEGER NOT NULL REFERENCES comunas(id),
  subtotal INTEGER NOT NULL CHECK (subtotal >= 0),
  costo_envio INTEGER NOT NULL CHECK (costo_envio >= 0),
  descuento INTEGER NOT NULL DEFAULT 0 CHECK (descuento >= 0),
  total INTEGER NOT NULL CHECK (total >= 0),
  estado TEXT NOT NULL DEFAULT 'pendiente'
    CHECK (estado IN ('pendiente', 'pagada', 'preparando', 'enviada', 'entregada', 'cancelada')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lineas_orden (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
  producto_id INTEGER REFERENCES productos(id),
  combo_id INTEGER REFERENCES combos(id),
  cantidad INTEGER NOT NULL CHECK (cantidad > 0),
  precio_unitario INTEGER NOT NULL CHECK (precio_unitario >= 0),
  CHECK ((producto_id IS NULL) <> (combo_id IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_lineas_combo_combo ON lineas_combo(combo_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_cliente ON ordenes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_estado ON ordenes(estado);
CREATE INDEX IF NOT EXISTS idx_lineas_orden_orden ON lineas_orden(orden_id);

CREATE TRIGGER IF NOT EXISTS productos_updated_at
AFTER UPDATE ON productos
BEGIN
  UPDATE productos SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS combos_updated_at
AFTER UPDATE ON combos
BEGIN
  UPDATE combos SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS costos_envio_updated_at
AFTER UPDATE ON costos_envio
BEGIN
  UPDATE costos_envio SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS clientes_updated_at
AFTER UPDATE ON clientes
BEGIN
  UPDATE clientes SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS ordenes_updated_at
AFTER UPDATE ON ordenes
BEGIN
  UPDATE ordenes SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

# === FIXTURES

CATEGORIAS = ["Bowls", "Bebestibles", "Snacks"]

# (nombre, ciudad, region, costo_envio)
COMUNAS = [
    ("Providencia", "Santiago", "Metropolitana", 1990),
    ("Ñuñoa", "Santiago", "Metropolitana", 1990),
    ("Las Condes", "Santiago", "Metropolitana", 2490),
    ("Santiago", "Santiago", "Metropolitana", 1990),
    ("La Florida", "Santiago", "Metropolitana", 2990),
    ("Maipú", "Santiago", "Metropolitana", 2990),
    ("Puente Alto", "Santiago", "Metropolitana", 3490),
    ("Viña del Mar", "Viña del Mar", "Valparaíso", 4990),
    ("Valparaíso", "Valparaíso", "Valparaíso", 4990),
]

# (nombre, descripcion, precio, stock, categoria)
PRODUCTOS = [
    ("Bowl Quinoa", "Quinoa, palta, garbanzos y salsa de yogurt", 6990, 20, "Bowls"),
    (
        "Bowl Pollo Teriyaki",
        "Arroz, pollo teriyaki y vegetales salteados",
        7490,
        20,
        "Bowls",
    ),
    ("Bowl Vegano", "Tofu, edamame, zanahoria y sésamo", 6790, 15, "Bowls"),
    ("Jugo Natural Naranja", "350 ml recién exprimido", 2500, 40, "Bebestibles"),
    ("Kombucha Jengibre", "Botella 330 ml", 2990, 30, "Bebestibles"),
    ("Agua Mineral", "500 ml", 1200, 60, "Bebestibles"),
    ("Mix Frutos Secos", "Bolsa 80 g", 1990, 50, "Snacks"),
    ("Barra de Granola", "Avena, miel y almendras", 1490, 50, "Snacks"),
]

# (nombre, descripcion, precio, [(producto, cantidad), ...])
COMBOS = [
    (
        "Combo Almuerzo",
        "Bowl Quinoa + Jugo Natural",
        8490,
        [("Bowl Quinoa", 1), ("Jugo Natural Naranja", 1)],
    ),
    (
        "Combo Fit",
        "Bowl Vegano + Kombucha + Mix Frutos Secos",
        10490,
        [("Bowl Vegano", 1), ("Kombucha Jengibre", 1), ("Mix Frutos Secos", 1)],
    ),
]


def ruta_db() -> Path:
    return Path(os.environ.get("TIENDA_DB", BASE_DIR / "tienda.db"))


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(ruta_db(), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # filas accesibles por nombre y convertibles a dict
    conn.execute("PRAGMA foreign_keys = ON")  # por conexión, siempre
    return conn


def inicializar() -> None:
    conn = conectar()
    try:
        conn.executescript(SCHEMA)
        sembrar(conn)
    finally:
        conn.close()


def sembrar(conn: sqlite3.Connection) -> None:
    with conn:
        if conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO categorias (nombre) VALUES (?)", [(c,) for c in CATEGORIAS]
            )

        if conn.execute("SELECT COUNT(*) FROM comunas").fetchone()[0] == 0:
            for nombre, ciudad, region, costo in COMUNAS:
                cur = conn.execute(
                    "INSERT INTO comunas (nombre, ciudad, region) VALUES (?, ?, ?)",
                    (nombre, ciudad, region),
                )
                conn.execute(
                    "INSERT INTO costos_envio (comuna_id, costo) VALUES (?, ?)",
                    (cur.lastrowid, costo),
                )

        if conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
            for nombre, descripcion, precio, stock, categoria in PRODUCTOS:
                cat_id = conn.execute(
                    "SELECT id FROM categorias WHERE nombre = ?", (categoria,)
                ).fetchone()["id"]
                conn.execute(
                    "INSERT INTO productos (nombre, descripcion, precio, stock, categoria_id) VALUES (?, ?, ?, ?, ?)",
                    (nombre, descripcion, precio, stock, cat_id),
                )

        if conn.execute("SELECT COUNT(*) FROM combos").fetchone()[0] == 0:
            for nombre, descripcion, precio, lineas in COMBOS:
                cur = conn.execute(
                    "INSERT INTO combos (nombre, descripcion, precio) VALUES (?, ?, ?)",
                    (nombre, descripcion, precio),
                )
                combo_id = cur.lastrowid
                for producto, cantidad in lineas:
                    prod_id = conn.execute(
                        "SELECT id FROM productos WHERE nombre = ?", (producto,)
                    ).fetchone()["id"]
                    conn.execute(
                        "INSERT INTO lineas_combo (combo_id, producto_id, cantidad) VALUES (?, ?, ?)",
                        (combo_id, prod_id, cantidad),
                    )


def get_db() -> Iterator[sqlite3.Connection]:
    conn = conectar()
    try:
        yield conn
    finally:
        conn.close()
