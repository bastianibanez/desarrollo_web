const archivos = {
  'producto:Bowl Quinoa': 'bowl-quinoa.webp',
  'producto:Bowl Pollo Teriyaki': 'bowl-pollo-teriyaki.webp',
  'producto:Bowl Vegano': 'bowl-vegano.webp',
  'producto:Bowl Salmón': 'bowl-salmon.webp',
  'producto:Bowl Mediterráneo': 'bowl-mediterraneo.webp',
  'producto:Bowl Frutas': 'bowl-frutas.webp',
  'producto:Bowl Granola': 'bowl-granola.webp',
  'producto:Jugo Natural Naranja': 'jugo-natural-naranja.webp',
  'producto:Kombucha Jengibre': 'kombucha-jengibre.webp',
  'producto:Agua Mineral': 'agua-mineral.webp',
  'producto:Batido Proteico': 'batido-proteico.webp',
  'producto:Jugo Verde': 'jugo-verde.webp',
  'producto:Té Helado Matcha': 'te-helado-matcha.webp',
  'producto:Agua de Coco': 'agua-coco.webp',
  'producto:Mix Frutos Secos': 'mix-frutos-secos.webp',
  'producto:Barra de Granola': 'barra-granola.webp',
  'producto:Chips de Kale': 'chips-kale.webp',
  'producto:Galletas de Avena': 'galletas-avena.webp',
  'producto:Hummus con Zanahoria': 'hummus-zanahoria.webp',
  'producto:Yogurt Griego': 'yogurt-griego.webp',
  'combo:Combo Almuerzo': 'combo-almuerzo.webp',
  'combo:Combo Fit': 'combo-fit.webp',
  'combo:Combo Power': 'combo-power.webp',
  'combo:Combo Veggie': 'combo-veggie.webp',
  'combo:Combo Desayuno': 'combo-desayuno.webp',
};

const baseImagenes = 'https://pub-1a2cdad7d229486fb35e3638126722d1.r2.dev';

export function imagenHero() {
  return `${baseImagenes}/hero-simple.webp`;
}

export function imagenDeItem(tipo, nombre) {
  const archivo = archivos[`${tipo}:${nombre}`];
  return archivo ? `${baseImagenes}/${archivo}` : undefined;
}
