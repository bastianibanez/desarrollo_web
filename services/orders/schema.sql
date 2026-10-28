CREATE TABLE IF NOT EXISTS comunas(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,ciudad TEXT NOT NULL,region TEXT NOT NULL,habilitada INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS costos_envio(id INTEGER PRIMARY KEY,comuna_id INTEGER NOT NULL UNIQUE REFERENCES comunas(id),costo INTEGER NOT NULL CHECK(costo>=0));
CREATE TABLE IF NOT EXISTS cajas(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL UNIQUE,cajero_id INTEGER);
CREATE TABLE IF NOT EXISTS ordenes(
 id INTEGER PRIMARY KEY,operacion_checkout TEXT NOT NULL UNIQUE,cliente_id INTEGER NOT NULL,
 cliente_snapshot TEXT NOT NULL,direccion_snapshot TEXT NOT NULL,comuna_id INTEGER NOT NULL REFERENCES comunas(id),
 caja_id INTEGER NOT NULL REFERENCES cajas(id),cajero_id INTEGER NOT NULL,cajero_identificador TEXT NOT NULL,
 reserva_id INTEGER UNIQUE,vence_en TEXT,checkout_completo INTEGER NOT NULL DEFAULT 0,
 subtotal INTEGER NOT NULL DEFAULT 0 CHECK(subtotal>=0),costo_envio INTEGER NOT NULL CHECK(costo_envio>=0),
 descuento INTEGER NOT NULL DEFAULT 0 CHECK(descuento=0),total INTEGER NOT NULL DEFAULT 0 CHECK(total>=0),moneda TEXT NOT NULL DEFAULT 'CLP',
 estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','pagado','preparando','enviado','entregado','cancelado','expirado')),
 version INTEGER NOT NULL DEFAULT 1,pago_en_proceso_id INTEGER,pago_confirmado_id INTEGER UNIQUE,pagado_en TEXT,
 causa_cancelacion TEXT,motivo_cancelacion TEXT,cancelado_por TEXT,cancelado_en TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lineas_orden(
 id INTEGER PRIMARY KEY,orden_id INTEGER NOT NULL REFERENCES ordenes(id),posicion INTEGER NOT NULL,
 producto_id INTEGER,combo_id INTEGER,nombre TEXT NOT NULL,cantidad INTEGER NOT NULL CHECK(cantidad>0),
 precio_unitario INTEGER NOT NULL CHECK(precio_unitario>=0),CHECK((producto_id IS NULL)!=(combo_id IS NULL)),UNIQUE(orden_id,posicion));
CREATE TABLE IF NOT EXISTS eventos_pedido(
 id INTEGER PRIMARY KEY,orden_id INTEGER NOT NULL REFERENCES ordenes(id),tipo TEXT NOT NULL,
 estado_anterior TEXT,estado TEXT NOT NULL,actor TEXT NOT NULL,motivo TEXT,referencia TEXT NOT NULL,
 fecha TEXT NOT NULL,UNIQUE(orden_id,tipo,referencia));
CREATE TABLE IF NOT EXISTS ventas(
 id INTEGER PRIMARY KEY,orden_id INTEGER NOT NULL UNIQUE REFERENCES ordenes(id),pago_id INTEGER NOT NULL UNIQUE,
 caja_id INTEGER NOT NULL REFERENCES cajas(id),cajero_id INTEGER NOT NULL,cajero_identificador TEXT NOT NULL,
 total INTEGER NOT NULL CHECK(total>=0),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comprobantes(
 id INTEGER PRIMARY KEY,venta_id INTEGER NOT NULL UNIQUE REFERENCES ventas(id),numero TEXT NOT NULL UNIQUE,
 contenido TEXT NOT NULL,emitido_en TEXT NOT NULL,estado_envio TEXT NOT NULL CHECK(estado_envio IN('pendiente','simulado','fallido')),
 mensaje_id TEXT NOT NULL UNIQUE,destinatario TEXT NOT NULL,intentos_envio INTEGER NOT NULL DEFAULT 0,ultimo_error TEXT);
CREATE INDEX IF NOT EXISTS orden_cliente ON ordenes(cliente_id,created_at,id);
CREATE INDEX IF NOT EXISTS orden_cola ON ordenes(estado,pagado_en,id);
CREATE INDEX IF NOT EXISTS eventos_orden ON eventos_pedido(orden_id,fecha,id);
CREATE INDEX IF NOT EXISTS ventas_fecha ON ventas(created_at,id);
