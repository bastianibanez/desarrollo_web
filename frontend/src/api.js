import { categorias, productos, combos } from './demo-datos.js';
import './demo.js';

const base = import.meta.env?.VITE_API_URL || 'http://localhost:8000/api';
export const API_BASE = base.endsWith('/') ? base.slice(0, -1) : base;
export const TOKEN_KEY = 'access_token';
const TIMEOUT_MS = 10000;
const REINTENTABLE = new Set([0, 503, 504]);

export class ApiError extends Error {
  constructor({ status, codigo, mensaje, requestId, retryAfter = null }) {
    super(mensaje || 'No se pudo completar la operación.');
    Object.assign(this, { status, codigo, requestId, retryAfter });
  }
}

async function enviar(path, options, requestId) {
  const headers = { 'Content-Type': 'application/json', 'X-Request-ID': requestId, ...options.headers };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(API_BASE + path, { ...options, headers, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (err) {
    throw new ApiError({ status: 0, codigo: err.name === 'TimeoutError' ? 'TIMEOUT_CLIENTE' : 'RED', requestId });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) sessionStorage.removeItem(TOKEN_KEY);
    throw new ApiError({
      status: res.status,
      codigo: data?.codigo || `HTTP_${res.status}`,
      mensaje: typeof data?.detail === 'string' ? data.detail : null,
      requestId: res.headers.get('X-Request-ID') || requestId,
      retryAfter: Number(res.headers.get('Retry-After')) || null,
    });
  }
  return data;
}

async function request(path, options = {}, { lectura = !options.method || options.method === 'GET', requestId = crypto.randomUUID() } = {}) {
  try {
    return await enviar(path, options, requestId);
  } catch (err) {
    if (!lectura || !REINTENTABLE.has(err.status)) throw err;
    await new Promise(r => setTimeout(r, 500));
    return enviar(path, options, requestId);
  }
}

const CODIGO_A_STATUS = { UNAUTHENTICATED: 401, FORBIDDEN: 403, TIMEOUT: 504, DEPENDENCY_UNAVAILABLE: 503 };
async function graphql(query, variables = {}) {
  const requestId = crypto.randomUUID();
  const result = await request('/graphql', { method: 'POST', body: JSON.stringify({ query, variables }) }, { lectura: true, requestId });
  if (result.errors?.length) {
    const issue = result.errors.find(e => e.extensions?.code === 'UNAUTHENTICATED') || result.errors[0];
    const codigo = issue.extensions?.code || 'FIELD_ERROR';
    if (codigo === 'UNAUTHENTICATED') sessionStorage.removeItem(TOKEN_KEY);
    throw new ApiError({ status: CODIGO_A_STATUS[codigo] || 400, codigo, mensaje: issue.message, requestId });
  }
  return result.data;
}

const copia = value => structuredClone(value);
const cliente = {
  id: 1, nombres: 'Camila', apellidos: 'Soto', rut: '12.345.678-5',
  email: 'camila@example.com', telefono: '+56 9 1234 5678',
  direccion: 'Av. Providencia 1234', comuna: 'Providencia', comuna_id: 1,
  activo: true, email_verificado_at: '2026-11-01T12:00:00-03:00',
};
const usuarios = [
  { id: 1, identificador: cliente.email, rol: 'cliente', activo: true },
  { id: 2, identificador: 'admin@example.com', rol: 'administrador', activo: true },
  { id: 3, identificador: 'caja@example.com', rol: 'cajero', activo: true },
  { id: 4, identificador: 'despacho@example.com', rol: 'despacho', activo: true },
];
const pedidos = [
  { id: '1003', estado: 'pagado', total: 9480, creadoEn: '2026-11-09T12:00:00-03:00', pagadoEn: '2026-11-09T12:05:00-03:00', ventaId: '503', pago: { id: '703', estado: 'aprobado' } },
  { id: '1002', estado: 'enviado', total: 10480, creadoEn: '2026-11-08T13:00:00-03:00', pagadoEn: '2026-11-08T13:05:00-03:00', ventaId: '502', pago: { id: '702', estado: 'aprobado' } },
  { id: '1001', estado: 'entregado', total: 9980, creadoEn: '2026-11-07T12:00:00-03:00', pagadoEn: '2026-11-07T12:05:00-03:00', ventaId: '501', pago: { id: '701', estado: 'aprobado' } },
];
export const getProductos = async () => copia(productos);
export const getCombos = async () => copia(combos);
export const getCategorias = async () => copia(categorias);
export const getClientes = async () => [copia(cliente)];
export const getUsuarios = async () => copia(usuarios);
export const getCajas = async () => [{ id: 1, nombre: 'Web', cajero_id: 3 }];
export const getPedidos = async (_rol, filtros = {}) => copia(pedidos.filter(p => !filtros.estado || p.estado === filtros.estado));
export const getPedido = async id => {
  const pedido = pedidos.find(p => p.id === String(id));
  if (!pedido) throw new Error('Este pedido no está incluido en la demo.');
  return copia(pedido);
};
export const getDespacho = async id => ({
  ...await getPedido(id), version: 1, cliente: copia(cliente),
  direccion: { calle: 'Av. Providencia', numero: '1234', departamento: '501', comuna: 'Providencia' },
  lineas: [{ nombre: 'Bowl Pollo Teriyaki', cantidad: 1 }],
});
export const getReporte = async (desde, hasta) => {
  const ventas = pedidos.filter(p => (!desde || p.pagadoEn.slice(0, 10) >= desde) && (!hasta || p.pagadoEn.slice(0, 10) <= hasta))
    .map(p => ({ id: p.ventaId, pedidoId: p.id, fecha: p.pagadoEn, total: p.total }));
  return { ventas, total: ventas.reduce((total, v) => total + v.total, 0) };
};
const soloLectura = async () => { throw new Error('Demo estática: esta acción no guarda cambios ni realiza cobros.'); };

export const login = datos => request('/login', { method: 'POST', body: JSON.stringify(datos) });
export const logout = () => request('/logout', { method: 'POST' });
export const obtenerPerfil = async () => {
  const { perfil } = await graphql(`{ perfil { id identificador rol clienteId correoVerificado datosCliente { nombres apellidos rut email telefono direccion comuna } } }`);
  return { ...perfil, perfil: perfil.datosCliente };
};

const enviarConClave = (path, body, clave) =>
  request(path, { method: 'POST', body: JSON.stringify(body), headers: { 'Idempotency-Key': clave } });

export const getComunas = () => request('/comunas');
export const registro = (datos, clave) => enviarConClave('/registro', datos, clave);
export const verificarCorreo = (datos, clave) => enviarConClave('/clientes/verificar-correo', datos, clave);
export const crearOrden = soloLectura;
export const iniciarPago = soloLectura;
export const crearCliente = soloLectura;
export const editarCliente = soloLectura;
export const crearUsuario = soloLectura;
export const editarUsuario = soloLectura;
export const crearProducto = soloLectura;
export const editarProducto = soloLectura;
export const eliminarProducto = soloLectura;
export const asignarCaja = soloLectura;
export const cancelarPedido = soloLectura;
export const avanzarPedido = soloLectura;
export const enviarComprobante = soloLectura;
