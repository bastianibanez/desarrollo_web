"""Datos ficticios conservados del catálogo original; sin credenciales."""

CATEGORIAS = ["Bowls", "Bebestibles", "Snacks"]

COMUNAS = [
    ("Providencia", "Santiago", "Metropolitana", 1990),
    ("Ñuñoa", "Santiago", "Metropolitana", 1990),
    ("Las Condes", "Santiago", "Metropolitana", 2490),
    ("Santiago", "Santiago", "Metropolitana", 1990),
    ("La Florida", "Santiago", "Metropolitana", 2990),
    ("Maipú", "Santiago", "Metropolitana", 2990),
    ("Puente Alto", "Santiago", "Metropolitana", 3490),
    ("Viña del Mar", "Viña del Mar", "Valparaíso", 4990),
    ("Valparaíso", "Valparaíso", "Valparaíso", 4990),
    ("Osorno", "Osorno", "Los Lagos", 7490),
]

PRODUCTOS = [
    ("Bowl Quinoa", "Quinoa, palta, garbanzos y salsa de yogurt", 6990, 20, "Bowls"),
    (
        "Bowl Pollo Teriyaki",
        "Arroz, pollo teriyaki y vegetales salteados",
        7490,
        20,
        "Bowls",
    ),
    ("Bowl Vegano", "Tofu, edamame, zanahoria y sésamo", 6790, 15, "Bowls"),
    ("Bowl Salmón", "Arroz integral, salmón, palta y pepino", 8490, 12, "Bowls"),
    ("Bowl Mediterráneo", "Cuscús, hummus, tomate y aceitunas", 6490, 15, "Bowls"),
    ("Bowl Frutas", "Frutilla, sandía, uva y melón", 4790, 15, "Bowls"),
    ("Bowl Granola", "Yogurt, arándano y granola", 4790, 15, "Bowls"),
    ("Jugo Natural Naranja", "350 ml recién exprimido", 2500, 40, "Bebestibles"),
    ("Kombucha Jengibre", "Botella 330 ml", 2990, 30, "Bebestibles"),
    ("Agua Mineral", "500 ml", 1200, 60, "Bebestibles"),
    (
        "Batido Proteico",
        "Plátano, avena y proteína whey, 400 ml",
        3490,
        25,
        "Bebestibles",
    ),
    (
        "Jugo Verde",
        "Espinaca, manzana, pepino y limón, 350 ml",
        2790,
        30,
        "Bebestibles",
    ),
    (
        "Té Helado Matcha",
        "Matcha con leche de almendras, 350 ml",
        2990,
        25,
        "Bebestibles",
    ),
    ("Agua de Coco", "Botella 330 ml", 1990, 40, "Bebestibles"),
    ("Mix Frutos Secos", "Bolsa 80 g", 1990, 50, "Snacks"),
    ("Barra de Granola", "Avena, miel y almendras", 1490, 50, "Snacks"),
    ("Chips de Kale", "Horneados, bolsa 40 g", 1790, 40, "Snacks"),
    ("Galletas de Avena", "Sin azúcar añadida, pack de 3", 1590, 45, "Snacks"),
    (
        "Hummus con Zanahoria",
        "Hummus 100 g con bastones de zanahoria",
        2290,
        30,
        "Snacks",
    ),
    ("Yogurt Griego", "Con miel y nueces, 150 g", 1890, 35, "Snacks"),
]

COMBOS = [
    (
        "Combo Almuerzo",
        "Bowl Quinoa + Jugo Natural",
        8490,
        [("Bowl Quinoa", 1), ("Jugo Natural Naranja", 1)],
    ),
    (
        "Combo Fit",
        "Bowl Vegano + Kombucha + Mix Frutos Secos",
        10490,
        [("Bowl Vegano", 1), ("Kombucha Jengibre", 1), ("Mix Frutos Secos", 1)],
    ),
    (
        "Combo Power",
        "Bowl Pollo Teriyaki + Batido Proteico + Barra de Granola",
        9990,
        [("Bowl Pollo Teriyaki", 1), ("Batido Proteico", 1), ("Barra de Granola", 1)],
    ),
    (
        "Combo Veggie",
        "Bowl Mediterráneo + Jugo Verde + Chips de Kale",
        9790,
        [("Bowl Mediterráneo", 1), ("Jugo Verde", 1), ("Chips de Kale", 1)],
    ),
    (
        "Combo Desayuno",
        "Bowl Granola + Té Helado Matcha + Galletas de Avena",
        7990,
        [("Bowl Granola", 1), ("Té Helado Matcha", 1), ("Galletas de Avena", 1)],
    ),
]

OFERTAS_PRODUCTOS = {
    "Bowl Quinoa": 5490,
    "Bowl Vegano": 5490,
    "Bowl Salmón": 6990,
    "Jugo Natural Naranja": 1990,
    "Mix Frutos Secos": 1590,
    "Barra de Granola": 990,
}

OFERTAS_COMBOS = {"Combo Power": 8490, "Combo Fit": 8990}
