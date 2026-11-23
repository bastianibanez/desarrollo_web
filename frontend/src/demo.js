if (typeof document !== 'undefined') {
  document.querySelectorAll('form:not(#reporte-form):not(#login-form)').forEach(form => {
    form.addEventListener('submit', event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
    form.querySelectorAll('[type="submit"]').forEach(boton => {
      boton.disabled = true;
      boton.title = 'Demo estática: no se guardan cambios ni se realizan cobros.';
    });
  });
}
