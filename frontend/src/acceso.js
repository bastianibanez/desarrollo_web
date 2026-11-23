import { getComunas, login, obtenerPerfil, TOKEN_KEY } from './api.js';
import { alerta } from './sesion.js';

const $ = id => document.getElementById(id);
const PAGINAS = new Set(['index.html', 'carrito.html', 'cuenta.html', 'panel.html']);
const params = new URLSearchParams(location.search);

// Solo páginas propias conocidas: evita una redirección abierta.
function destino(rol) {
  const volver = params.get('volver');
  if (PAGINAS.has(volver)) return volver;
  return rol === 'cliente' ? 'cuenta.html' : 'panel.html';
}

for (const comuna of await getComunas()) {
  $('reg-comuna').add(new Option(comuna.nombre, comuna.id));
}

$('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    const r = await login({ username: f.identificador, password: f.password });
    sessionStorage.setItem(TOKEN_KEY, r.access_token);
    const usuario = await obtenerPerfil();
    location.replace(destino(usuario.rol));
  } catch (err) {
    alerta('acceso-alert', 'danger', err.message);
    boton.disabled = false;
  }
});
