export const leerCarrito = () => JSON.parse(localStorage.getItem('carrito')) ?? [];

const guardar = (items) => localStorage.setItem('carrito', JSON.stringify(items));
const buscar = (items, tipo, id) => items.find((i) => i.tipo === tipo && i.id === id);

export function agregarAlCarrito(tipo, { id, nombre, descripcion, precio }) {
  const items = leerCarrito();
  const item = buscar(items, tipo, id);
  if (item) item.cantidad++;
  else items.push({ tipo, id, nombre, descripcion, precio, cantidad: 1 });
  guardar(items);
}

export function cambiarCantidad(tipo, id, delta) {
  const items = leerCarrito();
  buscar(items, tipo, id).cantidad += delta;
  guardar(items.filter((i) => i.cantidad > 0));
}

export function quitarDelCarrito(tipo, id) {
  guardar(leerCarrito().filter((i) => !(i.tipo === tipo && i.id === id)));
}

export const vaciarCarrito = () => localStorage.removeItem('carrito');
