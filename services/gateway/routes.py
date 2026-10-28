"""Lista explícita de exposición. Las lecturas GraphQL y rutas internas no se publican."""

# método, ruta pública sin /api, destino, roles (None = anónimo)
ROUTES = [
    ("POST", "/login", "auth", None),
    (
        "POST",
        "/logout",
        "auth",
        ("cliente", "administrador", "cajero", "despacho", "dueno"),
    ),
    ("POST", "/registro", "clients", None),
    ("POST", "/clientes/verificar-correo", "clients", None),
    ("GET", "/admin/clientes", "clients", ("administrador",)),
    ("POST", "/admin/clientes", "clients", ("administrador",)),
    ("PATCH", "/admin/clientes/{id}", "clients", ("administrador",)),
    ("GET", "/admin/usuarios", "clients", ("administrador",)),
    ("POST", "/admin/usuarios", "clients", ("administrador",)),
    ("PATCH", "/admin/usuarios/{id}", "clients", ("administrador",)),
    ("POST", "/productos", "inventory", ("administrador", "dueno")),
    ("PUT", "/productos/{id}", "inventory", ("administrador", "dueno")),
    ("DELETE", "/productos/{id}", "inventory", ("administrador", "dueno")),
    ("GET", "/comunas", "orders", None),
    ("POST", "/ordenes", "orders", ("cliente",)),
    ("POST", "/ordenes/{id}/cancelaciones", "orders", ("cliente", "administrador")),
    ("POST", "/ordenes/{id}/preparacion", "orders", ("despacho",)),
    ("POST", "/ordenes/{id}/envios", "orders", ("despacho",)),
    ("POST", "/ordenes/{id}/entregas", "orders", ("despacho",)),
    ("GET", "/ordenes/{id}/orden-despacho", "orders", ("despacho",)),
    ("GET", "/cajas", "orders", ("administrador", "cajero")),
    ("PATCH", "/cajas/{id}", "orders", ("administrador",)),
    ("POST", "/ventas/{id}/comprobantes", "orders", ("cajero",)),
    (
        "GET",
        "/ventas/{id}/comprobante",
        "orders",
        ("cliente", "cajero", "administrador"),
    ),
    ("POST", "/ventas/{id}/comprobante/envios", "orders", ("cajero",)),
    ("POST", "/pagos", "payments", ("cliente", "cajero")),
    ("GET", "/pagos/{id}", "payments", ("cliente", "cajero", "administrador")),
    ("POST", "/webhooks/pagos/{proveedor}", "payments", None),
    ("POST", "/solicitudes-reembolso", "payments", ("cliente",)),
    ("GET", "/solicitudes-reembolso", "payments", ("cliente", "administrador")),
    ("GET", "/solicitudes-reembolso/{id}", "payments", ("cliente", "administrador")),
    ("POST", "/solicitudes-reembolso/{id}/decisiones", "payments", ("administrador",)),
    ("POST", "/reembolsos/{id}/reintentos", "payments", ("administrador",)),
    ("POST", "/graphql", "graphql", None),
]

# La página del proveedor es una excepción pública de demostración, con token opaco.
SIMULATOR_ROUTES = [
    ("GET", "/simulador/pagos/checkout/{token}", "simulator", None),
    ("POST", "/simulador/pagos/checkout/{token}/resultado", "simulator", None),
]
