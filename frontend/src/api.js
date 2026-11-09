// Adaptador de presentación: datos locales, sin red ni autenticación real.
import { categorias, productos, combos, comunas } from './demo-datos.js';
import './demo.js';

export const TOKEN_KEY = 'fitexpress-demo';
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
export const getComunas = async () => copia(comunas);
export const getClientes = async () => [copia(cliente)];
export const getUsuarios = async () => copia(usuarios);
export const yo = async () => copia({
  ...usuarios[globalThis.location?.pathname.endsWith('/panel.html') ? 1 : 0],
  clienteId: 1, correoVerificado: true, perfil: cliente,
});
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
export const login = soloLectura;
export const logout = soloLectura;
export const registro = soloLectura;
export const verificarCorreo = soloLectura;
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
