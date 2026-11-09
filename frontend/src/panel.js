import {
  crearCliente, crearProducto, crearUsuario, editarCliente, editarProducto,
  editarUsuario, eliminarProducto, getCategorias, getClientes, getComunas,
  getProductos, getUsuarios, yo, getCajas, asignarCaja, cancelarPedido,
  getReporte, getPedidos, getDespacho, avanzarPedido, iniciarPago, enviarComprobante,
} from './api.js';
import { formatearPrecio } from './formato.js';
import { validarRut } from './rut.js';
import { alerta, cerrarSesion, irAAcceso } from './sesion.js';

const $ = (id) => document.getElementById(id);
const aviso = (tipo, mensaje) => {
  alerta('panel-alert', tipo, mensaje);
  $('panel-alert').scrollIntoView({ behavior: 'smooth', block: 'center' });
};

// --- Helpers para armar tablas sin insertar HTML (los textos vienen de usuarios) ---
function celda(contenido, clase = '') {
  const td = document.createElement('td');
  if (clase) td.className = clase;
  td.append(contenido ?? '');
  return td;
}

function insignia(texto, tipo) {
  const span = document.createElement('span');
  span.className = `badge text-bg-${tipo}`;
  span.textContent = texto;
  return span;
}

function boton(texto, clase, alHacerClick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `btn btn-sm btn-${clase}`;
  b.textContent = texto;
  b.addEventListener('click', alHacerClick);
  if (['Eliminar', 'Activar', 'Desactivar', 'Iniciar pago'].includes(texto)) {
    b.disabled = true;
    b.title = 'Demo estática: acción de ejemplo';
  }
  return b;
}

function acciones(...botones) {
  const td = document.createElement('td');
  td.className = 'text-end';
  botones.forEach((b, i) => td.append(...(i ? [' ', b] : [b])));
  return td;
}

function llenarTabla(id, filas, columnas) {
  if (filas.length === 0) {
    const td = celda('Sin registros', 'text-body-secondary');
    td.colSpan = columnas;
    const tr = document.createElement('tr');
    tr.append(td);
    $(id).replaceChildren(tr);
    return;
  }
  $(id).replaceChildren(...filas);
}

const fila = (...celdas) => {
  const tr = document.createElement('tr');
  tr.append(...celdas);
  return tr;
};

// Ejecuta una acción, muestra el mensaje de éxito o el error, y sale si la sesión venció
async function intentar(accion, exito) {
  try {
    await accion();
    if (exito) aviso('success', exito);
  } catch (err) {
    if (err.status === 401) irAAcceso();
    else aviso('danger', err.message);
  }
}

function rellenar(form, datos) {
  for (const [campo, valor] of Object.entries(datos)) {
    const el = form.elements.namedItem(campo);
    if (el) el.value = valor ?? '';
  }
  form.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

const cargarSelect = (id, items, texto) => {
  for (const item of items) $(id).add(new Option(texto(item), item.id));
};

// --- Clientes ---
async function cargarClientes() {
  const clientes = await getClientes();
  llenarTabla('admin-clientes', clientes.map(filaCliente), 7);
}

function filaCliente(c) {
  const activo = Boolean(c.activo);
  return fila(
    celda(c.id),
    celda(`${c.nombres} ${c.apellidos}`),
    celda(c.rut),
    celda(c.email),
    celda(c.email_verificado_at ? insignia('Sí', 'success') : insignia('Pendiente', 'warning')),
    celda(activo ? insignia('Activo', 'success') : insignia('Inactivo', 'secondary')),
    acciones(
      boton('Editar', 'outline-secondary', () => rellenar($('admin-cliente-form'), c)),
      boton(activo ? 'Desactivar' : 'Activar', activo ? 'outline-danger' : 'outline-success', () =>
        intentar(async () => {
          await editarCliente(c.id, { activo: !activo });
          await cargarClientes();
        }, activo ? 'Cliente desactivado' : 'Cliente activado')),
    ),
  );
}

$('ac-rut').addEventListener('input', (e) => {
  e.target.setCustomValidity(validarRut(e.target.value) ? '' : 'RUT inválido');
});

$('admin-cliente-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const { id, ...datos } = Object.fromEntries(new FormData(e.target));
  datos.comuna_id = Number(datos.comuna_id);
  intentar(async () => {
    if (id) await editarCliente(id, datos);
    else await crearCliente(datos);
    e.target.reset();
    await cargarClientes();
  }, id ? 'Cliente actualizado' : 'Cliente registrado: se envió el enlace de confirmación a su correo');
});

// --- Usuarios (funcionarios) ---
async function cargarUsuarios() {
  const usuarios = await getUsuarios();
  llenarTabla('admin-usuarios', usuarios.map(filaUsuario), 5);
}

function filaUsuario(u) {
  const activo = Boolean(u.activo);
  return fila(
    celda(u.id),
    celda(u.identificador),
    celda(u.rol),
    celda(activo ? insignia('Activo', 'success') : insignia('Inactivo', 'secondary')),
    acciones(
      boton('Editar', 'outline-secondary', () =>
        rellenar($('admin-usuario-form'), { id: u.id, identificador: u.identificador, rol: u.rol, password: '' })),
      boton(activo ? 'Desactivar' : 'Activar', activo ? 'outline-danger' : 'outline-success', () =>
        intentar(async () => {
          await editarUsuario(u.id, { activo: !activo });
          await cargarUsuarios();
        }, activo ? 'Usuario desactivado' : 'Usuario activado')),
    ),
  );
}

$('admin-usuario-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const { id, password, ...datos } = Object.fromEntries(new FormData(e.target));
  if (!id && !password) {
    aviso('danger', 'La contraseña inicial es obligatoria al crear un usuario');
    return;
  }
  if (password) datos.password = password;
  intentar(async () => {
    if (id) await editarUsuario(id, datos);
    else await crearUsuario(datos);
    e.target.reset();
    await cargarUsuarios();
  }, id ? 'Usuario actualizado' : 'Usuario creado');
});

// --- Productos ---
async function cargarProductos() {
  const productos = await getProductos(true);
  llenarTabla('admin-productos', productos.map(filaProducto), 7);
}

function filaProducto(p) {
  return fila(
    celda(p.id),
    celda(p.nombre),
    celda(p.categoria),
    celda(formatearPrecio(p.precio), 'text-end'),
    celda(p.precio_oferta != null ? formatearPrecio(p.precio_oferta) : '—', 'text-end'),
    celda(p.stock > 0 ? String(p.stock) : insignia('Agotado', 'danger'), 'text-end'),
    acciones(
      boton('Editar', 'outline-secondary', () => rellenar($('producto-form'), p)),
      boton('Eliminar', 'outline-danger', () => {
        if (!confirm(`¿Eliminar "${p.nombre}"?`)) return;
        intentar(async () => {
          await eliminarProducto(p.id);
          await cargarProductos();
        }, 'Producto eliminado');
      }),
    ),
  );
}

$('producto-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const datos = {
    nombre: f.nombre,
    descripcion: f.descripcion || null,
    precio: Number(f.precio),
    precio_oferta: f.precio_oferta === '' ? null : Number(f.precio_oferta),
    stock: Number(f.stock),
    categoria_id: Number(f.categoria_id),
  };
  intentar(async () => {
    if (f.id) await editarProducto(f.id, datos);
    else await crearProducto(datos);
    e.target.reset();
    await cargarProductos();
  }, f.id ? 'Producto actualizado' : 'Producto creado');
});

// --- Caja, reportes y despacho ---
let cajaId;
let seleccionado;
const fecha = value => value ? new Date(value).toLocaleString('es-CL') : '—';
async function cargarCaja() {
  const [cajas, usuarios] = await Promise.all([getCajas(), getUsuarios()]);
  const caja = cajas.find(c => c.nombre === 'Web');
  cajaId = caja?.id;
  $('caja-actual').textContent = usuarios.find(u => u.id === caja?.cajero_id)?.identificador || 'Sin asignar';
  $('caja-cajero').replaceChildren(new Option('Elige un cajero', ''));
  cargarSelect('caja-cajero', usuarios.filter(u => u.rol === 'cajero' && u.activo), u => u.identificador);
}
$('caja-form').addEventListener('submit', e => {
  e.preventDefault();
  intentar(async () => {
    if (!cajaId) throw new Error('Caja Web no disponible');
    await asignarCaja(cajaId, $('caja-cajero').value);
    await cargarCaja();
  }, 'Cajero asignado');
});
$('admin-anular-form').addEventListener('submit', e => {
  e.preventDefault();
  intentar(() => cancelarPedido($('an-orden').value, $('an-motivo').value), 'Pedido anulado');
});
$('reporte-form').addEventListener('submit', e => {
  e.preventDefault();
  intentar(async () => {
    const reporte = await getReporte($('rep-desde').value, $('rep-hasta').value);
    llenarTabla('reporte-ventas', reporte.ventas.map(v => fila(celda(v.id), celda(fecha(v.fecha)),
      celda(v.pedidoId), celda(formatearPrecio(v.total), 'text-end'))), 4);
    $('reporte-total').textContent = formatearPrecio(reporte.total);
  });
});
async function cargarPagos() {
  const pedidos = await getPedidos('cajero', { estado: 'pendiente' });
  llenarTabla('caja-pendientes', pedidos.map(p => fila(celda(p.id), celda(p.estado), celda(fecha(p.creadoEn)),
    celda(formatearPrecio(p.total), 'text-end'), celda(p.pago?.estado || 'Sin pago'),
    acciones(boton('Iniciar pago', 'success', () => intentar(async () => {
      const pago = await iniciarPago(p.id);
      if (!/^\/simulador\/pagos\/checkout\/[a-f0-9]+$/.test(pago.checkout_url)) throw new Error('Enlace de pago inválido');
      aviso('info', 'Abre el simulador y actualiza la lista al terminar.');
      const enlace = document.createElement('a');
      enlace.href = pago.checkout_url;
      enlace.target = '_blank';
      enlace.rel = 'noopener noreferrer';
      enlace.textContent = ' Abrir pago simulado';
      $('panel-alert').append(enlace);
    }))))), 6);
}
$('comprobante-form').addEventListener('submit', e => {
  e.preventDefault();
  intentar(() => enviarComprobante($('comp-venta').value), 'Comprobante emitido y envío simulado registrado');
});
async function cargarDespachos() {
  const pedidos = await getPedidos('despacho');
  llenarTabla('despacho-cola', pedidos.filter(p => p.estado !== 'entregado').map(p => fila(
    celda(p.id), celda(fecha(p.pagadoEn)), celda(p.estado),
    acciones(boton('Ver', 'outline-success', () => intentar(() => seleccionarPedido(p.id))))
  )), 4);
}
async function seleccionarPedido(id) {
  seleccionado = await getDespacho(id);
  const p = seleccionado;
  $('oi-numero').textContent = p.id;
  $('oi-pagado').textContent = fecha(p.pagadoEn);
  $('oi-cliente').textContent = `${p.cliente.nombres} ${p.cliente.apellidos}`;
  $('oi-direccion').textContent = [p.direccion.calle, p.direccion.numero, p.direccion.departamento, p.direccion.comuna].filter(Boolean).join(' ');
  llenarTabla('oi-items', p.lineas.map(l => fila(celda(l.nombre), celda(l.cantidad, 'text-end'))), 2);
  $('btn-imprimir').disabled = false;
  $('btn-preparando').disabled = !['pagado', 'preparando', 'enviado'].includes(p.estado);
  $('btn-preparando').textContent = { pagado: 'Preparando', preparando: 'Marcar enviado', enviado: 'Marcar entregado' }[p.estado] || 'Entregado';
}
$('btn-imprimir').addEventListener('click', () => { if (seleccionado) window.print(); });
$('btn-preparando').addEventListener('click', () => intentar(async () => {
  if (!seleccionado) return;
  const p = seleccionado;
  const accion = { pagado: 'preparacion', preparando: 'envios', enviado: 'entregas' }[p.estado];
  if (!accion) return;
  await avanzarPedido(p.id, accion, p.version);
  await seleccionarPedido(p.id);
  await cargarDespachos();
}, 'Estado actualizado'));
$('actualizar-pagos').addEventListener('click', () => intentar(cargarPagos));
$('actualizar-despachos').addEventListener('click', () => intentar(cargarDespachos));

// --- Pestañas según el rol ---
function mostrarSegunRol(rol) {
  document.querySelectorAll('[data-roles]').forEach((el) => {
    el.hidden = !el.dataset.roles.split(' ').includes(rol);
  });
  const primera = document.querySelector('li[data-roles]:not([hidden]) button');
  if (primera) bootstrap.Tab.getOrCreateInstance(primera).show();
}

$('btn-logout').addEventListener('click', cerrarSesion);

try {
  const usuario = await yo();
  if (usuario.rol === 'cliente') {
    location.href = 'cuenta.html';
  } else {
    $('panel-usuario').textContent = `${usuario.identificador} · ${usuario.rol}`;
    mostrarSegunRol(usuario.rol);

    if (usuario.rol === 'administrador') {
      cargarSelect('ac-comuna', await getComunas(), (c) => c.nombre);
      await intentar(cargarClientes);
      await intentar(cargarUsuarios);
      await intentar(cargarCaja);
      $('rep-desde').value = '2026-11-01';
      $('rep-hasta').value = '2026-11-30';
      $('reporte-form').dispatchEvent(new Event('submit', { cancelable: true }));
    }
    if (usuario.rol === 'cajero') await intentar(cargarPagos);
    if (usuario.rol === 'despacho') await intentar(cargarDespachos);
    if (usuario.rol === 'administrador' || usuario.rol === 'dueno') {
      cargarSelect('pr-categoria', await getCategorias(), (c) => c.nombre);
      await intentar(cargarProductos);
    }
  }
} catch (err) {
  if (err.status === 401) irAAcceso();
  else aviso('danger', err.message);
}
