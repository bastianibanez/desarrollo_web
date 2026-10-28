CREATE TABLE IF NOT EXISTS sesiones(
 token_hash TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL,
 version_cuenta TEXT NOT NULL, creado_en TEXT NOT NULL, expira_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS sesiones_usuario ON sesiones(usuario_id);
