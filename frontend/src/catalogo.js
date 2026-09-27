import { getProductos, getCombos } from './api.js';
import { formatearPrecio } from './formato.js';
import { agregarAlCarrito } from './carrito.js';
import { actualizarBadge } from './nav.js';

const combos = await getCombos();
const productos = await getProductos();

renderSeccion('combos', combos, 'combo');
for (const seccion of ['bowls', 'bebestibles', 'snacks']) {
  const items = productos.filter((p) => p.categoria.toLowerCase());
  renderSeccion(seccion, items, 'producto');
}

function renderSeccion(seccion, items, tipo) {
  const carousel = document.getElementById(`carousel-${seccion}`);
  const inner = carousel.querySelector('.carousel-inner');

  for (let i = 0; i < items.length; i += 4) {
    const slide = document.createElement('div');
    slide.className = i === 0 ? 'carousel-item active' : 'carousel-item';
    slide.innerHTML = '<div class="row row-cols-2 row-cols-md-4 g-3 g-lg-4"></div>'
    for (const item of items.slice(i, i + 4)) {
      slide.firstElementChild.append(crearCard(item, tipo));
    }
    inner.append(slide);
  }

  new bootstrap.Carousel(carousel, { interval: false });
}

function crearCard(item, tipo) {
  const col = document.createElement('div');
  col.className = 'col';
  col.innerHTML = `
    <div class="card h-100">
      <div class="product-placeholder rounded-top d-flex align-items-center justify-content-center">
        <span class="small">Imagen pendiente</span>
      </div>
      <div class="card-body d-flex flex-column">
        <h3 class="h6 card-title"></h3>
        <p class="small text-body-secondary flex-grow-1"></p>
        <div class="d-flex justify-content-between align-items-center">
          <span class="fw-semibold precio"></span>
          <button class="btn btn-sm btn-success" type="button">Agregar</button>
        </div>
      </div>
    </div>`;
  col.querySelector('h3').textContent = item.nombre;
  col.querySelector('p').textContent = item.descripcion;
  col.querySelector('.precio').textContent = formatearPrecio(item.precio);
  col.querySelector('button').addEventListener('click', () => {
    agregarAlCarrito(tipo, item);
    actualizarBadge();
  });
  return col;
}
