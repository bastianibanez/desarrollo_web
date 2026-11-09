// Controles de la maqueta, sin tokens ni sesiones del servidor.
if (typeof document !== 'undefined') {
  const cerrar = document.getElementById('btn-logout');
  if (cerrar) { cerrar.disabled = true; cerrar.textContent = 'Sesión demo'; }
  // Mantiene habilitada la consulta del reporte; las escrituras son solo una maqueta.
  document.querySelectorAll('form:not(#reporte-form)').forEach(form => {
    form.addEventListener('submit', event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
    form.querySelectorAll('[type="submit"]').forEach(boton => {
      boton.disabled = true;
      boton.title = 'Demo estática: no se guardan cambios ni se realizan cobros.';
    });
  });
}
