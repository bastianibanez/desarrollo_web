CREATE TABLE IF NOT EXISTS transacciones(
 id TEXT PRIMARY KEY,referencia TEXT NOT NULL UNIQUE,token_hash TEXT NOT NULL UNIQUE,monto INTEGER NOT NULL CHECK(monto>=0),
 moneda TEXT NOT NULL,estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN('pendiente','aprobado','rechazado')),
 aprobado_en TEXT,created_at TEXT NOT NULL,fallos_reembolso INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS devoluciones(
 id TEXT PRIMARY KEY,clave TEXT NOT NULL UNIQUE,transaccion_id TEXT NOT NULL REFERENCES transacciones(id),
 monto INTEGER NOT NULL,estado TEXT NOT NULL CHECK(estado IN('completado','fallido')),completado_en TEXT,created_at TEXT NOT NULL);
