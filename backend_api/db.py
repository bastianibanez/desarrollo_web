import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# === Tablas ===

CATEGORIAS = """
CREATE TABLE IF NOT EXISTS categorias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

PRODUCTOS = """
CREATE TABLE IF NOT EXISTS productos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  precio INTEGER NOT NULL CHECK (precio >= 0),
  precio_oferta INTEGER CHECK (precio_oferta >= 0 AND precio_oferta < precio),
  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  categoria_id INTEGER NOT NULL REFERENCES categorias(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

COMBOS = """
CREATE TABLE IF NOT EXISTS combos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  descripcion TEXT,
  precio INTEGER NOT NULL CHECK (precio >= 0),
  precio_oferta INTEGER CHECK (precio_oferta >= 0 AND precio_oferta < precio),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

LINEAS_COMBO = """
CREATE TABLE IF NOT EXISTS lineas_combo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  combo_id INTEGER NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad INTEGER NOT NULL DEFAULT 1 CHECK (cantidad > 0),
  UNIQUE (combo_id, producto_id)
);
"""

COMUNAS = """
CREATE TABLE IF NOT EXISTS comunas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  ciudad TEXT NOT NULL,
  region TEXT NOT NULL
);
"""

COSTOS_ENVIO = """
CREATE TABLE IF NOT EXISTS costos_envio (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  comuna_id INTEGER NOT NULL UNIQUE REFERENCES comunas(id),
  costo INTEGER NOT NULL CHECK (costo >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

LINEAS_ORDEN = """
CREATE TABLE IF NOT EXISTS lineas_orden (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
  producto_id INTEGER REFERENCES productos(id),
  combo_id INTEGER REFERENCES combos(id),
  cantidad INTEGER NOT NULL CHECK (cantidad > 0),
  precio_unitario INTEGER NOT NULL CHECK (precio_unitario >= 0),
  CHECK ((producto_id IS NULL) <> (combo_id IS NULL))
);
"""

CLIENTES = """
CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombres TEXT NOT NULL,
  apellidos TEXT NOT NULL,
  rut TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  telefono TEXT,
  direccion TEXT,
  comuna_id INTEGER REFERENCES comunas(id),
  provincia TEXT,
  region TEXT,
  fecha_nacimiento TEXT,
  sexo TEXT,
  email_verificado_at TEXT,
  codigo_hash TEXT,
  codigo_expira_at TEXT,
  intentos_codigo INTEGER NOT NULL DEFAULT 0,
  activo INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

USUARIOS = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cliente_id INTEGER UNIQUE REFERENCES clientes(id),
  identificador TEXT NOT NULL UNIQUE,
  password_hash TEXT,
  rol TEXT NOT NULL CHECK (rol IN
    ('cliente','administrador','cajero','despacho','dueno')),
  activo INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

SESIONES = """
CREATE TABLE IF NOT EXISTS sesiones (
  token_hash TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
  expira_at TEXT NOT NULL
);
"""

CAJAS = """
CREATE TABLE IF NOT EXISTS cajas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE,
  cajero_id INTEGER REFERENCES usuarios(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

ORDENES = """
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
    CHECK (estado IN ('pendiente','pagada','preparando',
                     'enviada','entregada','cancelada')),
  paid_at TEXT,
  ultimo_pago_resultado TEXT,
  motivo_anulacion TEXT,
  anulada_at TEXT,
  anulada_por INTEGER REFERENCES usuarios(id),
  impresa_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

VENTAS = """
CREATE TABLE IF NOT EXISTS ventas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER NOT NULL UNIQUE REFERENCES ordenes(id),
  caja_id INTEGER NOT NULL REFERENCES cajas(id),
  cajero_id INTEGER NOT NULL REFERENCES usuarios(id),
  total INTEGER NOT NULL CHECK (total >= 0),
  created_at TEXT NOT NULL,
  anulada_at TEXT,
  comprobante_emitido_at TEXT,
  comprobante_enviado_at TEXT,
  ultimo_error_correo TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

TABLAS = [
    CATEGORIAS,
    PRODUCTOS,
    COMBOS,
    LINEAS_COMBO,
    COMUNAS,
    COSTOS_ENVIO,
    CLIENTES,
    USUARIOS,
    SESIONES,
    CAJAS,
    ORDENES,
    LINEAS_ORDEN,
    VENTAS,
]


# === Indices ===

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);",
    "CREATE INDEX IF NOT EXISTS idx_lineas_combo_combo ON lineas_combo(combo_id);",
    "CREATE INDEX IF NOT EXISTS idx_ordenes_cliente ON ordenes(cliente_id);",
    "CREATE INDEX IF NOT EXISTS idx_ordenes_estado ON ordenes(estado);",
    "CREATE INDEX IF NOT EXISTS idx_lineas_orden_orden ON lineas_orden(orden_id);",
    "CREATE INDEX IF NOT EXISTS idx_usuarios_cliente ON usuarios(cliente_id);",
    "CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones(usuario_id);",
    "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_ventas_caja ON ventas(caja_id);",
]

# === Triggers ===

PRODUCTO_ACTUALIZADO = """
CREATE TRIGGER IF NOT EXISTS productos_updated_at
AFTER UPDATE ON productos
BEGIN
  UPDATE productos SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

COMBO_ACTUALIZADO = """
CREATE TRIGGER IF NOT EXISTS combos_updated_at
AFTER UPDATE ON combos
BEGIN
  UPDATE combos SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

COSTO_ENVIO_ACTUALIZADO = """
CREATE TRIGGER IF NOT EXISTS costos_envio_updated_at
AFTER UPDATE ON costos_envio
BEGIN
  UPDATE costos_envio SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

CLIENTE_ACTUALIZADO = """
CREATE TRIGGER IF NOT EXISTS clientes_updated_at
AFTER UPDATE ON clientes
BEGIN
  UPDATE clientes SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

ORDEN_ACTUALIZADA = """
CREATE TRIGGER IF NOT EXISTS ordenes_updated_at
AFTER UPDATE ON ordenes
BEGIN
  UPDATE ordenes SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

USUARIO_ACTUALIZADO = """
CREATE TRIGGER IF NOT EXISTS usuarios_updated_at
AFTER UPDATE ON usuarios
BEGIN
  UPDATE usuarios SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

CAJA_ACTUALIZADA = """
CREATE TRIGGER IF NOT EXISTS cajas_updated_at
AFTER UPDATE ON cajas
BEGIN
  UPDATE cajas SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

VENTA_ACTUALIZADA = """
CREATE TRIGGER IF NOT EXISTS ventas_updated_at
AFTER UPDATE ON ventas
BEGIN
  UPDATE ventas SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

TRIGGERS = [
    PRODUCTO_ACTUALIZADO,
    COMBO_ACTUALIZADO,
    COSTO_ENVIO_ACTUALIZADO,
    CLIENTE_ACTUALIZADO,
    ORDEN_ACTUALIZADA,
    USUARIO_ACTUALIZADO,
    CAJA_ACTUALIZADA,
    VENTA_ACTUALIZADA,
]

# === Esquema ===

SCHEMA = "\n\n".join(TABLAS + INDICES + TRIGGERS)

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
    ("Osorno", "Osorno", "Los Lagos", 7490),
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
    ("Bowl Salmón", "Arroz integral, salmón, palta y pepino", 8490, 12, "Bowls"),
    ("Bowl Mediterráneo", "Cuscús, hummus, tomate y aceitunas", 6490, 15, "Bowls"),
    ("Bowl Frutas", "Frutilla, sandía, uva y melón", 4790, 15, "Bowls"),
    ("Bowl Granola", "Yogurt, arándano y granola", 4790, 15, "Bowls"),
    ("Jugo Natural Naranja", "350 ml recién exprimido", 2500, 40, "Bebestibles"),
    ("Kombucha Jengibre", "Botella 330 ml", 2990, 30, "Bebestibles"),
    ("Agua Mineral", "500 ml", 1200, 60, "Bebestibles"),
    (
        "Batido Proteico",
        "Plátano, avena y proteína whey, 400 ml",
        3490,
        25,
        "Bebestibles",
    ),
    (
        "Jugo Verde",
        "Espinaca, manzana, pepino y limón, 350 ml",
        2790,
        30,
        "Bebestibles",
    ),
    (
        "Té Helado Matcha",
        "Matcha con leche de almendras, 350 ml",
        2990,
        25,
        "Bebestibles",
    ),
    ("Agua de Coco", "Botella 330 ml", 1990, 40, "Bebestibles"),
    ("Mix Frutos Secos", "Bolsa 80 g", 1990, 50, "Snacks"),
    ("Barra de Granola", "Avena, miel y almendras", 1490, 50, "Snacks"),
    ("Chips de Kale", "Horneados, bolsa 40 g", 1790, 40, "Snacks"),
    ("Galletas de Avena", "Sin azúcar añadida, pack de 3", 1590, 45, "Snacks"),
    (
        "Hummus con Zanahoria",
        "Hummus 100 g con bastones de zanahoria",
        2290,
        30,
        "Snacks",
    ),
    ("Yogurt Griego", "Con miel y nueces, 150 g", 1890, 35, "Snacks"),
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
    (
        "Combo Power",
        "Bowl Pollo Teriyaki + Batido Proteico + Barra de Granola",
        9990,
        [("Bowl Pollo Teriyaki", 1), ("Batido Proteico", 1), ("Barra de Granola", 1)],
    ),
    (
        "Combo Veggie",
        "Bowl Mediterráneo + Jugo Verde + Chips de Kale",
        9790,
        [("Bowl Mediterráneo", 1), ("Jugo Verde", 1), ("Chips de Kale", 1)],
    ),
    (
        "Combo Desayuno",
        "Bowl Granola + Té Helado Matcha + Galletas de Avena",
        7990,
        [("Bowl Granola", 1), ("Té Helado Matcha", 1), ("Galletas de Avena", 1)],
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

        conn.execute("INSERT OR IGNORE INTO cajas (nombre) VALUES ('Web')")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = conectar()
    try:
        yield conn
    finally:
        conn.close()


if __name__ == "__main__":
    print(SCHEMA)
