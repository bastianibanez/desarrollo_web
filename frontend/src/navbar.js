import { ROL_KEY, TOKEN_KEY } from './api.js';

export function mostrarNavegacion() {
  const rol = sessionStorage.getItem(TOKEN_KEY) ? sessionStorage.getItem(ROL_KEY) : null;
  const visible = { anonimo: !rol, cliente: rol === 'cliente', interno: Boolean(rol) && rol !== 'cliente' };
  for (const item of document.querySelectorAll('[data-nav]')) item.hidden = !visible[item.dataset.nav];
}

mostrarNavegacion();
