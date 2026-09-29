import {
  crearCliente, crearProducto, crearUsuario, editarCliente, editarProducto,
  editarUsuario, eliminarProducto, getCategorias, getClientes, getComunas,
  getProductos, getUsuarios, yo,
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
  const productos = await getProductos();
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
    }
    if (usuario.rol === 'administrador' || usuario.rol === 'dueno') {
      cargarSelect('pr-categoria', await getCategorias(), (c) => c.nombre);
      await intentar(cargarProductos);
    }
  }
} catch (err) {
  if (err.status === 401) irAAcceso();
  else aviso('danger', err.message);
}
