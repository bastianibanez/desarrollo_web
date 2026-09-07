const { DatabaseSync } = require('node:sqlite');

const db = new DatabaseSync('tienda.db');

db.exec(`
  CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    precio INTEGER NOT NULL,
    stock INTEGER NOT NULL
  )
`);

module.exports = db;
