import { getComunas, login, registro } from './api.js';
import { validarRut } from './rut.js';
import { alerta } from './sesion.js';

const $ = (id) => document.getElementById(id);
const aviso = (tipo, mensaje) => {
  alerta('acceso-alert', tipo, mensaje);
  $('acceso-alert').scrollIntoView({ behavior: 'smooth', block: 'center' });
};

try {
  for (const c of await getComunas()) {
    $('reg-comuna').add(new Option(c.nombre, c.id));
  }
} catch (err) {
  aviso('danger', err.message);
}

$('reg-rut').addEventListener('input', (e) => {
  e.target.setCustomValidity(validarRut(e.target.value) ? '' : 'RUT inválido');
});

$('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    const r = await login({ identificador: f.identificador, password: f.password });
    sessionStorage.setItem('sesion', r.sesion);
    location.href = r.rol === 'cliente' ? 'cuenta.html' : 'panel.html';
  } catch (err) {
    aviso('danger', err.message);
    boton.disabled = false;
  }
});

$('registro-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(e.target));
  datos.comuna_id = Number(datos.comuna_id);
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    await registro(datos);
    aviso('success', `Te enviamos un enlace de confirmación a ${datos.email}. Ábrelo para elegir tu contraseña.`);
    e.target.reset();
  } catch (err) {
    aviso('danger', err.message);
  } finally {
    boton.disabled = false;
  }
});
