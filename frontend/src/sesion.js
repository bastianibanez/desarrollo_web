import { logout, obtenerPerfil, TOKEN_KEY } from './api.js';

const INICIO = { cliente: 'cuenta.html', administrador: 'panel.html', cajero: 'panel.html', despacho: 'panel.html', dueno: 'panel.html' };
const nunca = () => new Promise(() => { });

export function irAAcceso(motivo = 'sin-sesion') {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem('compra-pendiente');
  const volver = location.pathname.split('/').pop() || 'index.html';
  location.replace(`acceso.html?motivo=${motivo}&volver=${encodeURIComponent(volver)}`);
  return nunca();
}

export async function requerirSesion(roles) {
  if (!sessionStorage.getItem(TOKEN_KEY)) return irAAcceso('sin-sesion');
  try {
    const usuario = await obtenerPerfil();
    if (roles && !roles.includes(usuario.rol)) {
      location.replace(`${INICIO[usuario.rol]}?motivo=sin-permiso`);
      return nunca();
    }
    return usuario;
  } catch (err) {
    if (err.status === 401) return irAAcceso('expirada');
    throw err;
  }
}

export async function cerrarSesion() {
  try { await logout(); } catch { /* si ya no valía en el servidor, igual se cierra aquí */ }
  sessionStorage.removeItem(TOKEN_KEY);
  location.replace('acceso.html?motivo=cerrada');
}

export function alerta(id, tipo, mensaje) {
  const caja = document.getElementById(id);
  caja.className = `alert alert-${tipo}`;
  caja.textContent = mensaje;
}
