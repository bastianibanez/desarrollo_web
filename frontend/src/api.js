const BASE = import.meta.env.VITE_API_URL;
const TOKEN = import.meta.env.VITE_CLIENT_TOKEN

async function request(path, options = {}) {
  const sesion = sessionStorage.getItem('sesion');
  const headers = {
    Authorization: `Bearer ${TOKEN}`,
    'Content-Type': 'application/json'
  };

  if (sesion) headers['X-User-Session'] = sesion;

  const res = await fetch(BASE + path, {
    ...options,
    headers
  });
  const data = await res.json();
  if (!res.ok) {
    const error = new Error(mensajeDeError(data.detail));
    error.status = res.status;
    throw error;
  }
  return data
}

// FastAPI responde con un texto, o con una lista de campos inválidos cuando es un 422
function mensajeDeError(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const campos = [...new Set(detail.map((e) => e.loc.at(-1)))];
    return `Revisa estos campos: ${campos.join(', ')}`;
  }
  return 'No se pudo completar la operación';
}

const enviar = (metodo, datos) => ({ method: metodo, body: JSON.stringify(datos) });

export const getProductos = () => request('/productos');
export const getCombos = () => request('/combos');
export const getComunas = () => request('/comunas');
export const getCategorias = () => request('/categorias');
export const crearOrden = (orden) =>
  request('/ordenes', { method: 'POST', body: JSON.stringify(orden) });

// Sesión y registro
export const login = (datos) => request('/login', enviar('POST', datos));
export const logout = () => request('/logout', { method: 'POST' });
export const yo = () => request('/yo');
export const registro = (datos) => request('/registro', enviar('POST', datos));
export const verificarCorreo = (datos) =>
  request('/clientes/verificar-correo', enviar('POST', datos));

// Mantenedores (administrador)
export const getClientes = () => request('/admin/clientes');
export const crearCliente = (datos) => request('/admin/clientes', enviar('POST', datos));
export const editarCliente = (id, datos) =>
  request(`/admin/clientes/${id}`, enviar('PATCH', datos));
export const getUsuarios = () => request('/admin/usuarios');
export const crearUsuario = (datos) => request('/admin/usuarios', enviar('POST', datos));
export const editarUsuario = (id, datos) =>
  request(`/admin/usuarios/${id}`, enviar('PATCH', datos));

// Productos (administrador o dueño)
export const crearProducto = (datos) => request('/productos', enviar('POST', datos));
export const editarProducto = (id, datos) =>
  request(`/productos/${id}`, enviar('PUT', datos));
export const eliminarProducto = (id) => request(`/productos/${id}`, { method: 'DELETE' });
