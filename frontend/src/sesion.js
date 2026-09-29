import { logout } from './api.js';

export function irAAcceso() {
  sessionStorage.removeItem('sesion');
  location.href = 'acceso.html';
}

export async function cerrarSesion() {
  try {
    await logout();
  } catch {
    // si la sesión ya no valía en el servidor, igual se cierra aquí
  }
  irAAcceso();
}

export function alerta(id, tipo, mensaje) {
  const caja = document.getElementById(id);
  caja.className = `alert alert-${tipo}`;
  caja.textContent = mensaje;
}
