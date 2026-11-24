import { logout, obtenerPerfil, ROL_KEY, TOKEN_KEY } from './api.js';
import { mostrarNavegacion } from './navbar.js';

const INICIO = { cliente: 'cuenta.html', administrador: 'panel.html', cajero: 'panel.html', despacho: 'panel.html', dueno: 'panel.html' };
const nunca = () => new Promise(() => { });

export function irAAcceso(motivo = 'sin-sesion') {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROL_KEY);
  sessionStorage.removeItem('compra-pendiente');
  const volver = location.pathname.split('/').pop() || 'index.html';
  location.replace(`acceso.html?motivo=${motivo}&volver=${encodeURIComponent(volver)}`);
  return nunca();
}

export async function requerirSesion(roles) {
  if (!sessionStorage.getItem(TOKEN_KEY)) return irAAcceso('sin-sesion');
  try {
    const usuario = await obtenerPerfil();
    sessionStorage.setItem(ROL_KEY, usuario.rol);
    mostrarNavegacion();
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
  await logout().catch(() => {});
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROL_KEY);
  location.replace('acceso.html?motivo=cerrada');
}

export function alerta(id, tipo, mensaje) {
  const caja = document.getElementById(id);
  caja.className = `alert alert-${tipo}`;
  caja.textContent = mensaje;
}

const MENSAJES = {
  RED: 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
  TIMEOUT_CLIENTE: 'El servidor tardó demasiado en responder. Inténtalo de nuevo.',
  DEPENDENCY_TIMEOUT: 'Un servicio interno tardó demasiado en responder. Inténtalo en unos minutos.',
  DEPENDENCY_UNAVAILABLE: 'Un servicio interno no está disponible. Inténtalo en unos minutos.',
  TIMEOUT: 'Un servicio interno tardó demasiado en responder. Inténtalo en unos minutos.',
  VAULT_UNAVAILABLE: 'El sistema no pudo validar su configuración interna. Inténtalo más tarde.',
  FORBIDDEN: 'Tu perfil no tiene permiso para esta acción.',
};

export function mensajeError(err) {
  const texto = err.status === 429
    ? `Demasiados intentos. Espera ${err.retryAfter || 60} segundos.`
    : MENSAJES[err.codigo] || err.message;
  return err.requestId ? `${texto} Código de seguimiento: ${err.requestId}` : texto;
}

const AVISOS = {
  'sin-sesion': ['info', 'Ingresa para continuar.'],
  expirada: ['warning', 'Tu sesión expiró. Ingresa nuevamente.'],
  cerrada: ['success', 'Cerraste sesión.'],
  'sin-permiso': ['warning', 'Tu perfil no tiene acceso a esa página.'],
};

export function mostrarMotivo(id) {
  const aviso = AVISOS[new URLSearchParams(location.search).get('motivo')];
  if (aviso) alerta(id, ...aviso);
}
