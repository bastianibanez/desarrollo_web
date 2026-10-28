CREATE TABLE IF NOT EXISTS clientes(
 id INTEGER PRIMARY KEY, nombres TEXT NOT NULL, apellidos TEXT NOT NULL,
 rut TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE COLLATE NOCASE, telefono TEXT,
 direccion TEXT, comuna_id INTEGER, comuna_nombre TEXT, provincia TEXT, region TEXT,
 fecha_nacimiento TEXT, sexo TEXT, activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN(0,1)),
 email_verificado_at TEXT, codigo_hash TEXT, codigo_expira_at TEXT,
 intentos_codigo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usuarios(
 id INTEGER PRIMARY KEY, cliente_id INTEGER UNIQUE REFERENCES clientes(id),
 identificador TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT,
 rol TEXT NOT NULL CHECK(rol IN('cliente','administrador','cajero','despacho','dueno')),
 activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN(0,1)), created_at TEXT NOT NULL,
 CHECK((rol='cliente' AND cliente_id IS NOT NULL) OR (rol!='cliente' AND cliente_id IS NULL)));
