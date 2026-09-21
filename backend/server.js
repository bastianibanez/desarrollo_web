const express = require('express');
const db = require('./db');

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }
  next();
});

app.get('/categorias', (req, res) => {
  res.json(db.prepare('SELECT * FROM categorias ORDER BY nombre').all());
});

app.get('/productos', (req, res) => {
  const productos = db
    .prepare(`
      SELECT p.*, c.nombre AS categoria
      FROM productos p
      JOIN categorias c ON c.id = p.categoria_id
      ORDER BY p.nombre
    `)
    .all();
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
  const { nombre, descripcion, precio, stock, categoria_id } = req.body;
  if (!nombre || precio == null || stock == null || categoria_id == null) {
    return res.status(400).json({ error: 'Faltan datos' });
  }
  const info = db
    .prepare('INSERT INTO productos (nombre, descripcion, precio, stock, categoria_id) VALUES (?, ?, ?, ?, ?)')
    .run(nombre, descripcion ?? null, precio, stock, categoria_id);
  res.status(201).json(db.prepare('SELECT * FROM productos WHERE id = ?').get(Number(info.lastInsertRowid)));
});

app.put('/productos/:id', (req, res) => {
  const { nombre, descripcion, precio, stock, categoria_id } = req.body;
  if (!nombre || precio == null || stock == null || categoria_id == null) {
    return res.status(400).json({ error: 'Faltan datos' });
  }
  const info = db
    .prepare('UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, stock = ?, categoria_id = ? WHERE id = ?')
    .run(nombre, descripcion ?? null, precio, stock, categoria_id, req.params.id);
  if (info.changes === 0) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  res.json(db.prepare('SELECT * FROM productos WHERE id = ?').get(req.params.id));
});

app.delete('/productos/:id', (req, res) => {
  const info = db.prepare('DELETE FROM productos WHERE id = ?').run(req.params.id);
  if (info.changes === 0) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  res.json({ ok: true });
});

app.get('/combos', (req, res) => {
  const combos = db.prepare('SELECT * FROM combos ORDER BY nombre').all();
  for (const combo of combos) {
    combo.productos = db
      .prepare(`
        SELECT p.id, p.nombre, lc.cantidad
        FROM lineas_combo lc
        JOIN productos p ON p.id = lc.producto_id
        WHERE lc.combo_id = ?
      `)
      .all(combo.id);
  }
  res.json(combos);
});

app.get('/comunas', (req, res) => {
  const comunas = db
    .prepare(`
      SELECT c.id, c.nombre, c.ciudad, c.region, e.costo AS costo_envio
      FROM comunas c
      JOIN costos_envio e ON e.comuna_id = c.id
      ORDER BY c.nombre
    `)
    .all();
  res.json(comunas);
});

app.post('/ordenes', (req, res) => {
  const { cliente, direccion, items } = req.body;

  if (!cliente || !direccion || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: 'Faltan datos' });
  }
  if (!cliente.nombres || !cliente.apellidos || !cliente.rut || !cliente.email) {
    return res.status(400).json({ error: 'Faltan datos del cliente' });
  }
  if (!direccion.calle || !direccion.numero || !direccion.comuna_id) {
    return res.status(400).json({ error: 'Faltan datos de la direccion' });
  }

  const envio = db.prepare('SELECT costo FROM costos_envio WHERE comuna_id = ?').get(direccion.comuna_id);
  if (!envio) {
    return res.status(400).json({ error: 'No hay despacho a esa comuna' });
  }

  const lineas = [];
  for (const item of items) {
    if (!item.cantidad || item.cantidad < 1) {
      return res.status(400).json({ error: 'Cantidad invalida' });
    }
    if (item.producto_id) {
      const producto = db.prepare('SELECT precio FROM productos WHERE id = ?').get(item.producto_id);
      if (!producto) {
        return res.status(400).json({ error: 'Producto no existe' });
      }
      lineas.push({ producto_id: item.producto_id, combo_id: null, cantidad: item.cantidad, precio: producto.precio });
    } else if (item.combo_id) {
      const combo = db.prepare('SELECT precio FROM combos WHERE id = ?').get(item.combo_id);
      if (!combo) {
        return res.status(400).json({ error: 'Combo no existe' });
      }
      lineas.push({ producto_id: null, combo_id: item.combo_id, cantidad: item.cantidad, precio: combo.precio });
    } else {
      return res.status(400).json({ error: 'Cada item necesita producto_id o combo_id' });
    }
  }

  const subtotal = lineas.reduce((suma, linea) => suma + linea.cantidad * linea.precio, 0);
  const total = subtotal + envio.costo;
  const rut = cliente.rut.replace(/\./g, '').toUpperCase();

  db.exec('BEGIN');
  try {
    let fila = db.prepare('SELECT id FROM clientes WHERE rut = ?').get(rut);
    if (!fila) {
      const info = db
        .prepare('INSERT INTO clientes (nombres, apellidos, rut, email, telefono) VALUES (?, ?, ?, ?, ?)')
        .run(cliente.nombres, cliente.apellidos, rut, cliente.email, cliente.telefono ?? null);
      fila = { id: Number(info.lastInsertRowid) };
    }

    const orden = db
      .prepare(`
        INSERT INTO ordenes (cliente_id, calle, numero, departamento, comuna_id, subtotal, costo_envio, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `)
      .run(
        fila.id,
        direccion.calle,
        direccion.numero,
        direccion.departamento ?? null,
        direccion.comuna_id,
        subtotal,
        envio.costo,
        total,
      );
    const ordenId = Number(orden.lastInsertRowid);

    const insertarLinea = db.prepare(`
      INSERT INTO lineas_orden (orden_id, producto_id, combo_id, cantidad, precio_unitario)
      VALUES (?, ?, ?, ?, ?)
    `);
    for (const linea of lineas) {
      insertarLinea.run(ordenId, linea.producto_id, linea.combo_id, linea.cantidad, linea.precio);
    }

    db.exec('COMMIT');
    res.status(201).json({ id: ordenId, subtotal, costo_envio: envio.costo, total });
  } catch (error) {
    db.exec('ROLLBACK');
    res.status(500).json({ error: 'No se pudo crear la orden' });
  }
});

app.get('/ordenes/:id', (req, res) => {
  const orden = db
    .prepare(`
      SELECT o.*, cl.nombres, cl.apellidos, cl.rut, cl.email, cl.telefono, cm.nombre AS comuna
      FROM ordenes o
      JOIN clientes cl ON cl.id = o.cliente_id
      JOIN comunas cm ON cm.id = o.comuna_id
      WHERE o.id = ?
    `)
    .get(req.params.id);
  if (!orden) {
    return res.status(404).json({ error: 'No encontrado' });
  }
  orden.lineas = db
    .prepare('SELECT producto_id, combo_id, cantidad, precio_unitario FROM lineas_orden WHERE orden_id = ?')
    .all(req.params.id);
  res.json(orden);
});

app.listen(3000, () => {
  console.log('Servidor en http://localhost:3000');
});
