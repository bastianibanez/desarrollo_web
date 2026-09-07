const express = require('express');
const db = require('./db');

const app = express();
app.use(express.json());

app.get('/productos', (req, res) => {
  const productos = db.prepare('SELECT * FROM productos').all();
  res.json(productos);
});

app.get('/productos/:id', (req, res) => {
  const producto = db.prepare('SELECT * FROM productos WHERE id = ?').get(req.params.id);
  if (!producto) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  res.json(producto);
});

app.post('/productos', (req, res) => {
  const { nombre, precio, stock } = req.body;
  if (!nombre || precio == null || stock == null) {
    return res.status(400).json({ error: 'Faltan datos' });
  }
  const info = db
    .prepare('INSERT INTO productos (nombre, precio, stock) VALUES (?, ?, ?)')
    .run(nombre, precio, stock);
  res.status(201).json({ id: Number(info.lastInsertRowid), nombre, precio, stock });
});

app.put('/productos/:id', (req, res) => {
  const { nombre, precio, stock } = req.body;
  if (!nombre || precio == null || stock == null) {
    return res.status(400).json({ error: 'Faltan datos' });
  }
  const info = db
    .prepare('UPDATE productos SET nombre = ?, precio = ?, stock = ? WHERE id = ?')
    .run(nombre, precio, stock, req.params.id);
  if (info.changes === 0) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  res.json({ id: Number(req.params.id), nombre, precio, stock });
});

app.delete('/productos/:id', (req, res) => {
  const info = db.prepare('DELETE FROM productos WHERE id = ?').run(req.params.id);
  if (info.changes === 0) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  res.json({ ok: true });
});

app.listen(3000, () => {
  console.log('Servidor en http://localhost:3000');
});
