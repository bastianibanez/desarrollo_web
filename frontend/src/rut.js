export function validarRut(rut) {
  const [cuerpo, dv] = rut.replaceAll('.', '').toUpperCase().split('-');
  let suma = 0;
  let mult = 2;
  for (const digito of [...cuerpo].reverse()) {
    suma += digito * mult;
    mult = mult === 7 ? 2 : mult + 1;
  }

  const r = 11 - (suma % 11);
  return dv === (r === 11 ? '0' : r === 10 ? 'K' : String(r));
}
