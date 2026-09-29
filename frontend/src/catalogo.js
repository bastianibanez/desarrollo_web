import { getProductos, getCombos } from './api.js';
import { formatearPrecio } from './formato.js';
import { agregarAlCarrito } from './carrito.js';
import { actualizarBadge } from './nav.js';
import { imagenDeItem, imagenHero } from './imagenes.js';

document.getElementById('hero-image').src = imagenHero();

const combos = await getCombos();
const productos = await getProductos();

// row-cols-2 bajo 768px, row-cols-md-4 desde ahí: cada slide trae una fila completa
const desktop = window.matchMedia('(min-width: 768px)');

function renderCatalogo() {
  renderSeccion('combos', combos, 'combo');
  for (const seccion of ['bowls', 'bebestibles', 'snacks']) {
    const items = productos.filter((p) => p.categoria.toLowerCase() === seccion);
    renderSeccion(seccion, items, 'producto');
  }
}

renderCatalogo();
desktop.addEventListener('change', renderCatalogo);

function renderSeccion(seccion, items, tipo) {
  const carousel = document.getElementById(`carousel-${seccion}`);
  const inner = carousel.querySelector('.carousel-inner');
  const porSlide = desktop.matches ? 4 : 2;
  inner.replaceChildren();

  for (let i = 0; i < items.length; i += porSlide) {
    const slide = document.createElement('div');
    slide.className = i === 0 ? 'carousel-item active' : 'carousel-item';
    slide.innerHTML = '<div class="row row-cols-2 row-cols-md-4 g-3 g-lg-4"></div>'
    for (const item of items.slice(i, i + porSlide)) {
      slide.firstElementChild.append(crearCard(item, tipo));
    }
    inner.append(slide);
  }

  bootstrap.Carousel.getOrCreateInstance(carousel, { interval: false });
}

function crearCard(item, tipo) {
  const col = document.createElement('div');
  col.className = 'col';
  col.innerHTML = `
    <div class="card h-100 position-relative">
      <span class="badge text-bg-success position-absolute top-0 start-0 m-2 d-none oferta-badge">Oferta</span>
      <div class="product-media"></div>
      <div class="card-body d-flex flex-column">
        <h3 class="h6 card-title"></h3>
        <p class="small text-body-secondary flex-grow-1"></p>
        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
          <div class="lh-sm precio-bloque">
            <del class="d-none small text-body-secondary precio-antes"></del>
            <span class="d-block fw-semibold precio"></span>
          </div>
          <button class="btn btn-sm btn-success" type="button">Agregar</button>
        </div>
      </div>
    </div>`;
  col.querySelector('h3').textContent = item.nombre;
  const media = col.querySelector('.product-media');
  const foto = imagenDeItem(tipo, item.nombre);
  if (foto) {
    const imagen = document.createElement('img');
    imagen.className = 'product-image rounded-top';
    imagen.src = foto;
    imagen.alt = item.nombre;
    imagen.loading = 'lazy';
    imagen.width = 400;
    imagen.height = 400;
    media.replaceWith(imagen);
  } else {
    media.className = 'product-placeholder rounded-top d-flex align-items-center justify-content-center';
    media.textContent = 'Imagen no disponible';
  }
  col.querySelector('p').textContent = item.descripcion;
  // precio_oferta solo llega para clientes registrados; si no viene, se muestra el precio normal
  const oferta = item.precio_oferta != null;
  const precioFinal = oferta ? item.precio_oferta : item.precio;
  col.querySelector('.precio').textContent = formatearPrecio(precioFinal);
  if (oferta) {
    col.querySelector('.precio').classList.add('text-success');
    col.querySelector('.oferta-badge').classList.remove('d-none');
    const antes = col.querySelector('.precio-antes');
    antes.textContent = formatearPrecio(item.precio);
    antes.classList.replace('d-none', 'd-block');
  }
  const disponible = tipo === 'combo' ? item.disponible : item.stock > 0;
  const boton = col.querySelector('button');
  if (!disponible) {
    boton.disabled = true;
    boton.textContent = 'Agotado';
  } else {
    boton.addEventListener('click', () => {
      agregarAlCarrito(tipo, { ...item, precio: precioFinal });
      actualizarBadge();
    });
  }
  return col;
}
