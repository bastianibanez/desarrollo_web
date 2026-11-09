import { getComunas, yo } from './api.js';
import { formatearPrecio } from './formato.js';
import { leerCarrito, cambiarCantidad, quitarDelCarrito } from './carrito.js';
import { actualizarBadge } from './nav.js';
import { imagenDeItem } from './imagenes.js';
import { irAAcceso } from './sesion.js';

const $ = (id) => document.getElementById(id);

let comunas = [];
try { comunas = await getComunas(); } catch (err) { alerta('danger', err.message); }
for (const c of comunas) {
  $('comuna').add(new Option(`${c.nombre}`, c.id));
}

// Los datos del comprador vienen del perfil autenticado.

try {
  const usuario = await yo();
  if (usuario.perfil) {
    const p = usuario.perfil;
    $('comprador-nombre').textContent = `${p.nombres} ${p.apellidos}`;
    $('comprador-rut').textContent = p.rut;
    $('comprador-email').textContent = p.email;
    $('comprador-telefono').textContent = p.telefono;
  } else {
    alerta('danger', 'Ingresa con una cuenta de cliente para crear un pedido.');
  }
} catch (err) {
  if (err.status === 401) irAAcceso();
  else alerta('danger', err.message);
}
render();

$('comuna').addEventListener('change', render);
$('carrito-lista').addEventListener('click', onClickLista);


function render() {
  const items = leerCarrito();
  $('carrito-lista').replaceChildren(...items.map(crearLinea));

  const subtotal = items.reduce((s, i) => s + i.precio * i.cantidad, 0);
  const comuna = comunas.find((c) => c.id === Number($('comuna').value));
  const envio = comuna ? comuna.costo_envio : 0;
  $('subtotal').textContent = formatearPrecio(subtotal);
  $('despacho').textContent = formatearPrecio(envio);
  $('total').textContent = formatearPrecio(subtotal + envio);

  $('btn-pagar').disabled = true;
  $('btn-pagar').textContent = 'Compra de ejemplo';
  $('pago-pendiente').hidden = true;

  actualizarBadge();
}

function crearLinea(item) {
  const li = document.createElement('li');
  li.className = 'list-group-item px-0 py-4 d-flex align-items-center gap-3';
  li.dataset.tipo = item.tipo;
  li.dataset.id = item.id;
  li.innerHTML = `
    <div class="product-media"></div>
    <div class="flex-grow-1">
      <h3 class="h6 mb-1"></h3>
      <p class="small text-body-secondary mb-2"></p>
      <div class="d-flex justify-content-between align-items-center small">
        <span class="fw-semibold precio"></span>
        <div class="d-flex align-items-center gap-2">
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-success" data-accion="menos">−</button>
            <span class="btn btn-outline-success disabled cantidad"></span>
            <button type="button" class="btn btn-outline-success" data-accion="mas">+</button>
          </div>
          <button type="button" class="btn btn-link btn-sm link-secondary" data-accion="quitar">Quitar</button>
        </div>
      </div>
    </div>`;
  li.querySelector('h3').textContent = item.nombre;
  const media = li.querySelector('.product-media');
  const foto = imagenDeItem(item.tipo, item.nombre);
  if (foto) {
    const imagen = document.createElement('img');
    imagen.className = 'product-image rounded-3';
    imagen.src = foto;
    imagen.alt = item.nombre;
    imagen.loading = 'lazy';
    imagen.width = 88;
    imagen.height = 88;
    media.replaceWith(imagen);
  } else {
    media.className = 'product-placeholder rounded-3 d-flex align-items-center justify-content-center p-2';
    media.textContent = 'Imagen no disponible';
  }
  li.querySelector('p').textContent = item.descripcion;
  li.querySelector('.cantidad').textContent = item.cantidad;
  li.querySelector('.precio').textContent = formatearPrecio(item.precio * item.cantidad);
  return li;
}

// Un solo listener para toda la lista: sigue funcionando aunque render() recree las líneas
function onClickLista(e) {
  const accion = e.target.dataset.accion;
  if (!accion) return;
  const { tipo, id } = e.target.closest('li').dataset;
  if (accion === 'mas') cambiarCantidad(tipo, Number(id), 1);
  if (accion === 'menos') cambiarCantidad(tipo, Number(id), -1);
  if (accion === 'quitar') quitarDelCarrito(tipo, Number(id));
  render();
}


function alerta(tipo, mensaje) {
  $('checkout-alert').className = `alert alert-${tipo}`;
  $('checkout-alert').textContent = mensaje;
}
