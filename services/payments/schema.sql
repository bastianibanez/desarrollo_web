CREATE TABLE IF NOT EXISTS pagos(
 id INTEGER PRIMARY KEY,pedido_id INTEGER NOT NULL,cliente_id INTEGER NOT NULL,caja_id INTEGER NOT NULL,cajero_id INTEGER NOT NULL,
 proveedor TEXT NOT NULL DEFAULT 'simulado',transaccion_id TEXT UNIQUE,checkout_url TEXT,
 estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','aprobado','rechazado')),
 monto INTEGER NOT NULL CHECK(monto>=0),moneda TEXT NOT NULL DEFAULT 'CLP',vence_en TEXT NOT NULL,
 aprobado_en TEXT,verificado_en TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,aceptado INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS pago_pendiente ON pagos(pedido_id) WHERE estado='pendiente';
CREATE TABLE IF NOT EXISTS solicitudes_reembolso(
 id INTEGER PRIMARY KEY,pedido_id INTEGER NOT NULL,pago_id INTEGER NOT NULL REFERENCES pagos(id),cliente_id INTEGER NOT NULL,
 motivo TEXT NOT NULL,estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','aprobada','rechazada')),
 decision_id TEXT UNIQUE,administrador_id INTEGER,motivo_decision TEXT,decidida_en TEXT,created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS solicitud_activa ON solicitudes_reembolso(pedido_id) WHERE estado IN('pendiente','aprobada');
CREATE TABLE IF NOT EXISTS reembolsos(
 id INTEGER PRIMARY KEY,pago_id INTEGER NOT NULL UNIQUE REFERENCES pagos(id),solicitud_id INTEGER UNIQUE REFERENCES solicitudes_reembolso(id),
 causa TEXT NOT NULL CHECK(causa IN('cancelacion_pagada','pago_tardio','cobro_duplicado','excepcional')),
 autorizacion TEXT NOT NULL,estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','completado','fallido')),
 monto_solicitado INTEGER NOT NULL CHECK(monto_solicitado>=0),monto_devuelto INTEGER NOT NULL DEFAULT 0,
 moneda TEXT NOT NULL DEFAULT 'CLP',completado_en TEXT,created_at TEXT NOT NULL,
 CHECK(monto_devuelto>=0 AND monto_devuelto<=monto_solicitado),CHECK((causa='excepcional')=(solicitud_id IS NOT NULL)));
CREATE TABLE IF NOT EXISTS intentos_reembolso(
 id INTEGER PRIMARY KEY,reembolso_id INTEGER NOT NULL REFERENCES reembolsos(id),numero INTEGER NOT NULL,
 referencia TEXT UNIQUE,clave TEXT NOT NULL UNIQUE,estado TEXT NOT NULL CHECK(estado IN('pendiente','completado','fallido')),
 iniciado_por INTEGER,error TEXT,verificado_en TEXT,created_at TEXT NOT NULL,UNIQUE(reembolso_id,numero));
CREATE TABLE IF NOT EXISTS eventos_proveedor(
 id INTEGER PRIMARY KEY,evento_id TEXT NOT NULL UNIQUE,tipo TEXT NOT NULL CHECK(tipo='pago'),
 transaccion_id TEXT NOT NULL,datos TEXT NOT NULL,recibido_en TEXT NOT NULL,procesado_en TEXT);
CREATE INDEX IF NOT EXISTS pagos_pedido ON pagos(pedido_id,created_at,id);
CREATE INDEX IF NOT EXISTS pagos_fecha ON pagos(aprobado_en);
CREATE INDEX IF NOT EXISTS reembolsos_fecha ON reembolsos(completado_en);
