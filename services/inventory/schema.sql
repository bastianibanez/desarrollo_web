CREATE TABLE IF NOT EXISTS categorias(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS productos(
 id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,descripcion TEXT,precio INTEGER NOT NULL CHECK(precio>=0),
 precio_oferta INTEGER CHECK(precio_oferta>=0 AND precio_oferta<precio),stock INTEGER NOT NULL CHECK(stock>=0),
 categoria_id INTEGER NOT NULL REFERENCES categorias(id),activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN(0,1)));
CREATE TABLE IF NOT EXISTS combos(
 id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,descripcion TEXT,precio INTEGER NOT NULL CHECK(precio>=0),
 precio_oferta INTEGER CHECK(precio_oferta>=0 AND precio_oferta<precio));
CREATE TABLE IF NOT EXISTS lineas_combo(
 id INTEGER PRIMARY KEY,combo_id INTEGER NOT NULL REFERENCES combos(id),producto_id INTEGER NOT NULL REFERENCES productos(id),
 cantidad INTEGER NOT NULL CHECK(cantidad>0),UNIQUE(combo_id,producto_id));
CREATE TABLE IF NOT EXISTS reservas(
 id INTEGER PRIMARY KEY,operacion_id TEXT NOT NULL UNIQUE,pedido_id INTEGER UNIQUE,
 estado TEXT NOT NULL CHECK(estado IN('activa','consumida','liberada','expirada','restituida')),
 creado_en TEXT NOT NULL,vence_en TEXT NOT NULL,consumo_operacion TEXT,version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS lineas_reserva(
 id INTEGER PRIMARY KEY,reserva_id INTEGER NOT NULL REFERENCES reservas(id),posicion INTEGER NOT NULL,
 producto_id INTEGER REFERENCES productos(id),combo_id INTEGER REFERENCES combos(id),
 nombre TEXT NOT NULL,cantidad INTEGER NOT NULL CHECK(cantidad>0),precio_unitario INTEGER NOT NULL CHECK(precio_unitario>=0),
 CHECK((producto_id IS NULL)!=(combo_id IS NULL)),UNIQUE(reserva_id,posicion));
CREATE TABLE IF NOT EXISTS detalles_reserva(
 id INTEGER PRIMARY KEY,reserva_id INTEGER NOT NULL REFERENCES reservas(id),producto_id INTEGER NOT NULL REFERENCES productos(id),
 cantidad INTEGER NOT NULL CHECK(cantidad>0),UNIQUE(reserva_id,producto_id));
CREATE INDEX IF NOT EXISTS reservas_expira ON reservas(estado,vence_en);
CREATE INDEX IF NOT EXISTS detalle_producto ON detalles_reserva(producto_id,reserva_id);
CREATE INDEX IF NOT EXISTS categoria_producto ON productos(categoria_id,activo);
