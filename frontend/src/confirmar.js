import { verificarCorreo } from './api.js';
import { alerta } from './sesion.js';

const $ = (id) => document.getElementById(id);

// El enlace del correo trae ?cliente=ID&codigo=NNNNNN
const params = new URLSearchParams(location.search);
const cliente = params.get('cliente') ?? '';
const codigo = params.get('codigo') ?? '';

if (/^\d+$/.test(cliente) && /^\d{6}$/.test(codigo)) {
  $('conf-cliente-id').value = cliente;
  $('conf-codigo').value = codigo;
  history.replaceState(null, '', location.pathname); // el código no queda en la barra de direcciones
} else {
  alerta('confirmar-alert', 'danger', 'El enlace está incompleto o no es válido. Usa el enlace del correo que recibiste.');
  $('confirmar-form').hidden = true;
}

$('confirmar-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const boton = e.target.querySelector('[type=submit]');
  boton.disabled = true;
  try {
    await verificarCorreo({
      cliente_id: Number(f.cliente_id),
      codigo: f.codigo,
      password: f.password,
    });
    $('confirmar-alert').className = '';
    $('confirmar-alert').textContent = '';
    $('confirmar-form').hidden = true;
    $('confirmar-listo').hidden = false;
  } catch (err) {
    alerta('confirmar-alert', 'danger', err.message);
    boton.disabled = false;
  }
});
