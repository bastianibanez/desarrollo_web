import { verificarCorreo } from './api.js';
import { alerta, mensajeError } from './sesion.js';

const $ = id => document.getElementById(id);
const esDigitos = (texto, largo) => texto.length > 0 && (!largo || texto.length === largo)
  && [...texto].every(c => c >= '0' && c <= '9');

const params = new URLSearchParams(location.search);
const cliente = params.get('cliente') ?? '';
const codigo = params.get('codigo') ?? '';
const clave = crypto.randomUUID();

if (esDigitos(cliente) && esDigitos(codigo, 6)) {
  $('conf-cliente-id').value = cliente;
  $('conf-codigo').value = codigo;
  history.replaceState(null, '', location.pathname);
} else {
  alerta('confirmar-alert', 'danger', 'El enlace está incompleto o no es válido. Usa el enlace del correo que recibiste.');
  $('confirmar-form').hidden = true;
}

$('confirmar-form').addEventListener('submit', async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    await verificarCorreo({ cliente_id: Number(f.cliente_id), codigo: f.codigo, password: f.password }, clave);
    $('confirmar-alert').className = '';
    $('confirmar-alert').textContent = '';
    $('confirmar-form').hidden = true;
    $('confirmar-listo').hidden = false;
  } catch (err) {
    alerta('confirmar-alert', 'danger', mensajeError(err));
    boton.disabled = false;
  }
});
