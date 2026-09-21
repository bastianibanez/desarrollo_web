const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const db = new DatabaseSync(path.join(__dirname, 'tienda.db'));

db.exec('PRAGMA foreign_keys = ON');

db.exec(`
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
`);

db.exec(`
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
`);

const categorias = ['Bowls', 'Bebestibles', 'Snacks'];

const comunas = [
  ['Providencia', 'Santiago', 'Metropolitana', 1990],
  ['Ñuñoa', 'Santiago', 'Metropolitana', 1990],
  ['Las Condes', 'Santiago', 'Metropolitana', 2490],
  ['Santiago', 'Santiago', 'Metropolitana', 1990],
  ['La Florida', 'Santiago', 'Metropolitana', 2990],
  ['Maipú', 'Santiago', 'Metropolitana', 2990],
  ['Puente Alto', 'Santiago', 'Metropolitana', 3490],
  ['Viña del Mar', 'Viña del Mar', 'Valparaíso', 4990],
  ['Valparaíso', 'Valparaíso', 'Valparaíso', 4990],
];

const sinCategorias = db.prepare('SELECT COUNT(*) AS total FROM categorias').get().total === 0;

if (sinCategorias) {
  const insertarCategoria = db.prepare('INSERT INTO categorias (nombre) VALUES (?)');
  for (const nombre of categorias) {
    insertarCategoria.run(nombre);
  }
}

const sinComunas = db.prepare('SELECT COUNT(*) AS total FROM comunas').get().total === 0;

if (sinComunas) {
  const insertarComuna = db.prepare('INSERT INTO comunas (nombre, ciudad, region) VALUES (?, ?, ?)');
  const insertarCosto = db.prepare('INSERT INTO costos_envio (comuna_id, costo) VALUES (?, ?)');
  for (const [nombre, ciudad, region, costo] of comunas) {
    const info = insertarComuna.run(nombre, ciudad, region);
    insertarCosto.run(Number(info.lastInsertRowid), costo);
  }
}

module.exports = db;
