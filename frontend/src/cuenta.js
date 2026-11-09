import { yo, getPedidos, cancelarPedido, iniciarPago } from './api.js';
import { alerta, cerrarSesion, irAAcceso } from './sesion.js';

const $ = (id) => document.getElementById(id);

$('btn-logout').addEventListener('click', cerrarSesion);

async function cargarPedidos() {
  const pedidos = await getPedidos('cliente');
  const filas = pedidos.map(p => {
    const tr = document.createElement('tr');
    for (const texto of [p.id, new Date(p.creadoEn).toLocaleString('es-CL'), p.estado,
      new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(p.total)]) {
      const td = document.createElement('td');
      td.textContent = texto;
      tr.append(td);
    }
    const motivo = document.createElement('td');
    const acciones = document.createElement('td');
    if (p.estado === 'pendiente') {
      const input = document.createElement('input');
      input.className = 'form-control form-control-sm';
      input.placeholder = 'Motivo';
      input.setAttribute('aria-label', `Motivo de anulación del pedido ${p.id}`);
      input.maxLength = 1000;
      motivo.append(input);
      for (const [titulo, accion] of [
        ['Pagar', async () => {
          const pago = await iniciarPago(p.id);
          if (!/^\/simulador\/pagos\/checkout\/[a-f0-9]+$/.test(pago.checkout_url)) throw new Error('Enlace de pago inválido');
          const enlace = document.createElement('a');
          enlace.href = pago.checkout_url;
          enlace.target = '_blank';
          enlace.rel = 'noopener noreferrer';
          enlace.textContent = ' Abrir pago simulado';
          alerta('cuenta-alert', 'info', 'Abre el simulador y luego actualiza tus pedidos.');
          $('cuenta-alert').append(enlace);
        }],
        ['Anular', async () => {
          if (!input.value.trim()) throw new Error('Indica el motivo de anulación.');
          await cancelarPedido(p.id, input.value);
          await cargarPedidos();
        }],
      ]) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'btn btn-sm btn-outline-success me-2';
        boton.textContent = titulo;
        boton.addEventListener('click', async () => {
          boton.disabled = true;
          try { await accion(); } catch (err) {
            if (err.status === 401) irAAcceso();
            else alerta('cuenta-alert', 'danger', err.message);
          } finally { boton.disabled = false; }
        });
        acciones.append(boton);
      }
    }
    tr.append(motivo, acciones);
    return tr;
  });
  if (!filas.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.textContent = 'Aún no tienes pedidos.';
    tr.append(td);
    filas.push(tr);
  }
  $('mis-ordenes').replaceChildren(...filas);
}
$('actualizar-pedidos').addEventListener('click', async () => {
  try { await cargarPedidos(); } catch (err) {
    if (err.status === 401) irAAcceso();
    else alerta('cuenta-alert', 'danger', err.message);
  }
});

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
    await cargarPedidos();
  }
} catch (err) {
  if (err.status === 401) irAAcceso();
  else alerta('cuenta-alert', 'danger', err.message);
}
