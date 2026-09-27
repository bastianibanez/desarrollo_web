const BASE = import.meta.env.VITE_API_URL;
const TOKEN = import.meta.env.VITE_CLIENT_TOKEN

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' }
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail);
  return data
}

export const getProductos = () => request('/productos');
export const getCombos = () => request('/combos');
export const getComunas = () => request('/comunas');
export const crearOrden = (orden) =>
  request('/', { method: 'POST', body: JSON.stringify(orden) });

