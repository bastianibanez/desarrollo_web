const { GraphQLScalarType, GraphQLError } = require('graphql');
const { error } = require('./context');

function camel(value) {
  if (Array.isArray(value)) return value.map(camel);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).map(([k, v]) => [k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()), camel(v)]));
}
function page(pagina, limite) {
  if (pagina < 1 || pagina > 1000000 || limite < 1 || limite > 50) throw error('Paginación inválida', 'BAD_USER_INPUT');
}
function field(obj, _, __, info) {
  const value = obj[info.fieldName];
  if (value instanceof GraphQLError) throw value;
  return value;
}
function financial(obj, args, q, info) {
  q.require();
  if (q.user.rol === 'despacho') throw error('Campo financiero no autorizado', 'FORBIDDEN');
  return field(obj, args, q, info);
}
async function finance(q, ids) {
  const data = await q.call('payments', 'POST', '/interno/pagos/consultas', { pedido_ids: ids });
  return new Map(data.items.map(x => [x.pedido_id, camel(x)]));
}
async function listOrders(_, { filtros, pagina = 1, limite = 20 }, q, info) {
  page(pagina, limite);
  q.require(info.fieldName === 'misPedidos' ? ['cliente'] : ['administrador', 'cajero', 'despacho']);
  const data = camel(await q.call('orders', 'GET', '/ordenes', null, { pagina, limite, ...filtros }));
  if (q.user.rol !== 'despacho' && data.items.length) {
    try {
      const payments = await finance(q, data.items.map(x => x.id));
      for (const item of data.items) item.pago = payments.get(item.id)?.pago;
    } catch (err) { for (const item of data.items) item.pago = err; }
  }
  return data;
}
const resolvers = {
  Dinero: new GraphQLScalarType({ name: 'Dinero', serialize: value => String(value) }),
  Query: {
    async catalogo(_, { filtros = {}, pagina = 1, limite = 12 }, q) {
      page(pagina, limite);
      function params(values = {}) {
        return { pagina, limite, producto_id: values.productoId, categoria_id: values.categoriaId, combo_id: values.comboId,
          busqueda: values.busqueda, solo_disponibles: values.soloDisponibles ?? false, incluir_inactivos: values.incluirInactivos ?? false };
      }
      const targets = [['categorias', '/categorias'], ['productos', '/productos', params(filtros?.productos)], ['combos', '/combos', params(filtros?.combos)]];
      const values = await Promise.allSettled(targets.map(([, path, par]) => q.call('inventory', 'GET', path, null, par)));
      return Object.fromEntries(targets.map(([name], i) => {
        const value = values[i];
        if (value.status === 'rejected') return [name, value.reason];
        if (name === 'productos') value.value.items = value.value.items.map(p => ({ ...p, categoria: { id: p.categoria_id, nombre: p.categoria } }));
        return [name, camel(value.value)];
      }));
    },
    async perfil(_, args, q) {
      q.require(); const data = await q.call('clients', 'GET', '/perfil');
      data.datos_cliente = data.perfil; delete data.perfil; return camel(data);
    },
    misPedidos: listOrders,
    pedidos: listOrders,
    async pedido(_, { id }, q) {
      q.require(['cliente', 'administrador', 'cajero', 'despacho']);
      if (!/^\d+$/.test(id) || Number(id) <= 0) throw error('ID inválido', 'BAD_USER_INPUT');
      const data = camel(await q.call('orders', 'GET', `/ordenes/${id}`)); data._id = id;
      if (q.user.rol !== 'despacho') {
        try {
          const f = (await finance(q, [Number(id)])).get(Number(id)) || {};
          data.pago = f.pago; data.reembolso = f.reembolso;
        } catch (err) { data.pago = err; data.reembolso = err; }
        try {
          const refs = [...new Map(data.lineas.map(x => [`${x.tipo}:${x.referenciaId}`, { tipo: x.tipo, id: Number(x.referenciaId) }])).values()];
          const result = await q.call('inventory', 'POST', '/interno/catalogo/consultas', { items: refs });
          const actual = new Map(result.items.map(x => [`${x.tipo}:${x.id}`, x.encontrado ? camel(x) : null]));
          for (const line of data.lineas) line.catalogoActual = actual.get(`${line.tipo}:${line.referenciaId}`);
        } catch (err) { for (const line of data.lineas) line.catalogoActual = err; }
      }
      return data;
    },
    async reporteVentas(_, { desde, hasta, pagina = 1, limite = 20 }, q) {
      page(pagina, limite); q.require(['administrador', 'dueno']);
      const result = { desde, hasta, zonaHoraria: 'America/Santiago', moneda: 'CLP' };
      const values = await Promise.allSettled([
        q.call('orders', 'GET', '/reportes/ventas', null, { desde, hasta, pagina, limite }),
        q.call('payments', 'GET', '/interno/reportes/movimientos', null, { desde, hasta })
      ]);
      const names = [['ventas', 'cantidadVentas'], ['totalCobrado', 'totalDevuelto', 'netoCobrado']];
      values.forEach((value, i) => {
        if (value.status === 'fulfilled') Object.assign(result, camel(value.value));
        else for (const name of names[i]) result[name] = value.reason;
      }); return result;
    }
  },
  Producto: { stock(obj, args, q) { q.require(['administrador', 'dueno']); return obj.stock; } },
  Catalogo: Object.fromEntries(['categorias', 'productos', 'combos'].map(x => [x, field])),
  ReporteVentas: Object.fromEntries(['ventas', 'cantidadVentas', 'totalCobrado', 'totalDevuelto', 'netoCobrado'].map(x => [x, field])),
  ResumenPedido: Object.fromEntries(['total', 'ventaId', 'pago'].map(x => [x, financial])),
  LineaPedido: Object.fromEntries(['precioUnitario', 'subtotal', 'catalogoActual'].map(x => [x, financial])),
  Pedido: {
    ...Object.fromEntries(['total', 'ventaId', 'pago', 'subtotal', 'descuento', 'costoEnvio', 'reembolso', 'comprobante'].map(x => [x, financial])),
    async historial(obj, { pagina = 1, limite = 20 }, q) {
      page(pagina, limite);
      return camel((await q.call('orders', 'GET', `/ordenes/${obj._id}`, null, { historial_pagina: pagina, historial_limite: limite })).historial);
    }
  }
};
module.exports = { resolvers };
