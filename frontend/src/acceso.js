import { getComunas, login, obtenerPerfil, registro, ROL_KEY, TOKEN_KEY } from './api.js';
import { validarRut } from './rut.js';
import { alerta, mensajeError, mostrarMotivo } from './sesion.js';

const $ = id => document.getElementById(id);
const PAGINAS = new Set(['index.html', 'carrito.html', 'cuenta.html', 'panel.html']);
const params = new URLSearchParams(location.search);

function destino(rol) {
  const volver = params.get('volver');
  if (PAGINAS.has(volver)) return volver;
  return rol === 'cliente' ? 'cuenta.html' : 'panel.html';
}

mostrarMotivo('acceso-alert');

let comunas = [];
try {
  comunas = await getComunas();
  for (const c of comunas) $('reg-comuna').add(new Option(c.nombre, c.id));
} catch (err) {
  alerta('acceso-alert', 'danger', `No se pudieron cargar las comunas. ${mensajeError(err)}`);
}

$('reg-comuna').addEventListener('change', e => {
  const c = comunas.find(x => x.id === Number(e.target.value));
  if (c) {
    $('reg-provincia').value = c.ciudad;
    $('reg-region').value = c.region;
  }
});

$('reg-rut').addEventListener('input', e => {
  e.target.setCustomValidity(validarRut(e.target.value) ? '' : 'RUT inválido');
});

let claveRegistro = crypto.randomUUID();
$('registro-form').addEventListener('submit', async e => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(e.target));
  datos.comuna_id = Number(datos.comuna_id);
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    await registro(datos, claveRegistro);
    claveRegistro = crypto.randomUUID();
    alerta('acceso-alert', 'success', `Te enviamos un código de confirmación a ${datos.email}.`);
    e.target.reset();
  } catch (err) {
    if (err.status >= 400 && err.status < 500) claveRegistro = crypto.randomUUID();
    alerta('acceso-alert', 'danger', mensajeError(err));
  } finally {
    boton.disabled = false;
  }
});

$('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    const r = await login({ username: f.identificador, password: f.password });
    sessionStorage.setItem(TOKEN_KEY, r.access_token);
    const usuario = await obtenerPerfil();
    sessionStorage.setItem(ROL_KEY, usuario.rol);
    location.replace(destino(usuario.rol));
  } catch (err) {
    alerta('acceso-alert', 'danger', mensajeError(err));
    const espera = err.status === 429 ? (err.retryAfter || 60) * 1000 : 0;
    setTimeout(() => { boton.disabled = false; }, espera);
  }
});
