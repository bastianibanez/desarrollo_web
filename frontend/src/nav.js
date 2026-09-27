import { leerCarrito } from './carrito.js';

export function actualizarBadge() {
  const n = leerCarrito().reduce((total, i) => total + i.cantidad, 0);
  document.getElementById('carrito-badge').textContent = n || '';
}

actualizarBadge();
