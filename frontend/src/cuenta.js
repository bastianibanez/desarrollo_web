import { yo } from './api.js';
import { alerta, cerrarSesion, irAAcceso } from './sesion.js';

const $ = (id) => document.getElementById(id);

$('btn-logout').addEventListener('click', cerrarSesion);

try {
  const usuario = await yo();
  if (usuario.rol !== 'cliente') {
    location.href = 'panel.html';
  } else {
    const p = usuario.perfil;
    $('dato-nombre').textContent = `${p.nombres} ${p.apellidos}`;
    $('dato-rut').textContent = p.rut;
    $('dato-email').textContent = p.email;
    $('dato-telefono').textContent = p.telefono;
    $('dato-direccion').textContent = [p.direccion, p.comuna].filter(Boolean).join(', ');
  }
} catch (err) {
  if (err.status === 401) irAAcceso();
  else alerta('cuenta-alert', 'danger', err.message);
}
