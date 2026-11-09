// Pantalla de acceso navegable en la demo estática.
import { getComunas } from './api.js';

for (const comuna of await getComunas()) {
  document.getElementById('reg-comuna').add(new Option(comuna.nombre, comuna.id));
}
