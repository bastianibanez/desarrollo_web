const clp = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' })

export const formatearPrecio = (n) => clp.format(n);
