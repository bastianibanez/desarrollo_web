# Contratos GraphQL de Fit Express

Diseño del 24 de octubre de 2026 tras la ronda de decisiones. Contrato para las seis consultas; sin mutations ni subscriptions en esta entrega. Los valores de los ejemplos son ficticios. **Implementación del 28 de octubre:** [SDL](../services/graphql/schema.graphql) y [resolvers Node/Apollo](../services/graphql/resolvers.js) en el backend nuevo; consultar [pruebas y límites de la ejecución](estado-backend-e2.md). No se conectó el frontend.

La fuente funcional es [reglas-pedidos.md](reglas-pedidos.md); los contratos privados y de acciones se describen en [contratos-rest.md](contratos-rest.md).

Implementación con Express/Apollo como el ejemplo del profesor. El gateway valida el Bearer en Auth y genera cabeceras de identidad para GraphQL; los resolvers propagan ese contexto autenticado a las APIs privadas. GraphQL no recibe el token personal ni consulta bases ajenas.

## Transporte y convenciones

- Endpoint externo único: `POST /api/graphql`; destino privado: `POST /graphql` (S41).
- `Content-Type: application/json`; cuerpo `{query, operationName, variables}`. La sesión personal viaja por `Authorization: Bearer <access_token>` desde sessionStorage, ocho horas fijas. No se envía el secreto de integración del gateway.
- Campos GraphQL en camelCase; APIs REST en snake_case. IDs GraphQL como cadenas, REST como enteros positivos salvo referencias opacas del proveedor.
- Fechas de entrada de filtros/reportes: `YYYY-MM-DD`; fechas de salida: ISO 8601 UTC. Días de negocio en `America/Santiago`, incluyendo desde/hasta con límite exclusivo al día siguiente. No usar un UTC offset fijo.
- Importes de productos/pedidos: `Int` en CLP sin decimales; validar rango de 32 bits al escribir y al calcular totales. `Dinero` serializa acumulados de reportes como cadena decimal entera, incluyendo signo para netos negativos, evitando overflow y floats.
- Página desde 1; catálogo 12 elementos por defecto y otros listados 20; máximo 50. Cada listado tiene su total filtrado antes de paginar. Página posterior al final: items vacío y total conservado. Parámetros nulos explícitos de página/límite o fuera de rango: entrada inválida.
- Campos nullable permiten restringir por rol o representar ausencia/fallo sin borrar el resto. `!` garantiza presencia cuando el objeto se devuelve correctamente; los errores propagan según el schema.

## Operaciones, argumentos y acceso

| ID | Operación | Argumentos y orden | Fuente y acceso |
| --- | --- | --- | --- |
| G01 | misPedidos | filtros opcionales: estado/desde/hasta; página/límite. Creación e ID descendentes. | Cliente propietario obtenido de la sesión. S21 + I16 por lote. |
| G02 | pedido | ID obligatorio; historial con página/límite propios. | S22 autoriza primero. Cliente propietario, Administrador, Cajero de su caja o Despacho con finalidad operativa. I04/I16 agrupados para actores autorizados. |
| G03 | catalogo | filtros separados por productos/combos; página/límite aplicados a cada listado seleccionado. Nombre e ID ascendentes. | Anónimo para campos públicos. S13–S16; stock e inactivos únicamente para Administrador/Dueño. |
| G04 | perfil | Sin ID de otro usuario ni otros argumentos. | Usuario autenticado; S03 de clients. Datos propios del perfil; datosCliente/correoVerificado pueden ser null para funcionarios sin cliente. |
| G05 | pedidos | filtros estado/desde/hasta y página/límite. Gestión: creación descendente; Despacho: confirmación de pago e ID ascendentes. | Administrador, Cajero de caja asignada o Despacho. S21 + I16 cuando corresponde; sin alcance ampliado por filtros. |
| G06 | reporteVentas | desde/hasta obligatorios, página/límite para ventas; no se pagina ni recalcula el agregado financiero. | Administrador/Dueño. S30 lista/cuenta ventas; I17 calcula total cobrado, devuelto y neto. |

Filtros de pedidos usan fecha de creación del pedido, independientemente del orden de presentación. Fechas desde/hasta opcionales se validan y, si están ambas, desde no supera hasta. La cola solo admite estados operativos autorizados de pedidos con pago confirmado. Los filtros nunca permiten a Despacho consultar pendientes/expirados ni pedidos cancelados fuera de su cola.

## Catálogo y precios

- Filtros de productos: ID, categoría, búsqueda en nombre/descripción, soloDisponibles. Búsqueda recortada, hasta 100 caracteres, sin distinguir mayúsculas. Condiciones combinadas con AND antes de paginar.
- Filtros de combos: ID, búsqueda y soloDisponibles; no heredan los filtros de categoría/productos. `soloDisponibles` es false por defecto: los agotados siguen visibles con Agregar deshabilitado.
- Categorías y combos quedan preconfigurados. ComponenteCombo.cantidad describe receta, no stock. Combo disponible solo si sus componentes activos tienen unidades libres suficientes, considerando reservas.
- `precio` es normal; `precioOferta` es null si no existe/no corresponde mostrarla; `precioFinal` lo calcula inventory para la identidad actual. Se mantiene la política existente: ofertas para Cliente verificado, Administrador y Dueño; otros reciben precio normal. No se expone una oferta por medio del precioFinal.
- Público recibe únicamente disponible, sin cantidades exactas. `stock` y `incluirInactivos` están restringidos a Administrador/Dueño. Seleccionarlos sin permiso produce PROHIBIDO; un parámetro privilegiado no se ignora silenciosamente. Activo es un indicador, sin agregar una operación de reactivación a este alcance.
- Retirados fuera del catálogo público. Orders conserva compras anteriores. Las imágenes siguen en frontend/src/imagenes.js; no se añade gestión de archivos.
- Se puede solicitar una página nueva únicamente de productos sin volver a solicitar combos. Los carruseles deben paginar por categoría, no asumir que los primeros 12 productos representan todas las categorías.

## Pedido, dinero y datos históricos

Orders conserva nombre/precio de las líneas, dirección/contacto necesarios de esa compra, tarifa, moneda, vencimiento, caja/cajero y fechas. El backend nuevo implementa snapshots, listado/historial, versionado y estados; el backend histórico se conserva sin migrar. Estos datos no se completan leyendo el perfil o catálogo actuales por JOIN.

`subtotal` es la suma de cantidad por precio unitario aceptado, incluidas las ofertas aplicadas; `descuento` solo representa otro descuento del pedido, actualmente cero. `total = subtotal - descuento + costoEnvio`. El envío proviene de la tarifa oficial por comuna; no se impone costo cero ni distancia. Los datos de catalogoActual son actuales y opcionales, nunca reemplazan la compra histórica.

`venceEn` conserva el vencimiento original; el contador solo se muestra en pendiente. `estado` usa los siete valores canónicos del schema. Se migrarán las variantes pagada/enviada/entregada/cancelada del backend. La devolución es independiente: un pedido puede ser entregado con reembolso completado.

Pago resume el cobro aprobado; si no existe, el intento más reciente. Un rechazo posterior no oculta un cobro aprobado. Sin intentos: pago null sin error. Reembolso resume el proceso vigente y montoDevuelto acumulado confirmado, sin archivos, motivos privados ni expediente de decisión. Sin devolución: null sin error. `reintentable` solo puede ser true para Administrador cuando S42 permite actuar; no sustituye la autorización en payments.

Historial contiene eventos operativos autorizados (estado/fecha), no comentarios internos. Comprobante aporta ventaId para descargar mediante S32, sin URLs a bases o servicios privados. No se incluye RUT, fecha de nacimiento o sexo en el detalle del pedido; el RUT propio se conserva en perfil para la pantalla existente.

### Proyección por actor

| Actor | Campos y recursos |
| --- | --- |
| Cliente | Solo sus pedidos: importes, nombre/contacto propios de compra, dirección, seguimiento, catálogo actual y resumen financiero/comprobante. |
| Administrador | Gestión de pedidos y evaluación/reintento financiero con campos necesarios. |
| Cajero | Caja asignada: líneas, importes, nombre del comprador, resumen financiero y comprobante. Teléfono/dirección no se devuelven por defecto. No decide reembolsos. |
| Despacho | Pedidos operativos pagados: ID, estado/fechas, nombres/cantidades de líneas, dirección/contacto necesarios e historial operativo. Sin totales, precios de líneas, catálogo comercial actual, ventaId, pago, reembolso o comprobante de venta. |
| Dueño | Perfil propio, catálogo/stock para administración y reporte; sin acceso general a pedidos individuales. |
| Visitante | Catálogo público; sin perfiles, pedidos ni finanzas. |

Campos restringidos nullable devuelven null con PROHIBIDO. Inexistente/ajeno para Cliente: mismo NO_ENCONTRADO y pedido null. Los resolvers cargan los enriquecimientos autorizados al resolver la página o pedido; GraphQL solo devuelve los campos solicitados. No hay optimización por selección de campos ni caché de tareas. I04 agrupa referencias tipo+ID; I16 agrupa pedidos y reutiliza su respuesta para pago/reembolso dentro de la misma operación.

## Reporte y fechas

Listado/cantidad corresponden a ventas registradas en orders durante el período. Total cobrado/devuelto/neto corresponden a movimientos verificados de payments por su propia fecha; un cobro tardío sin venta válida también es un movimiento financiero. Por eso no se exige igualdad entre suma de filas y totalCobrado del período.

Una venta del lunes devuelta el martes conserva el cobro en lunes y la devolución en martes. Neto puede ser negativo. Payments calcula neto como cobrado menos devuelto una sola vez. Si falta I17, los tres indicadores son null con error, no cero; la UI indica reporte incompleto. Orders y payments pueden devolver sus partes autorizadas independientemente. No hay rankings ni desglose diario/por producto.

## Schema de contrato

Este SDL define las seis queries y tipos objetivo. No instala librerías ni implementa resolvers. Las siguientes convenciones técnicas completan el diseño derivado de las decisiones, sin afirmar que se probaron en el backend.

```graphql
scalar Dinero

enum EstadoPedido { pendiente pagado preparando enviado entregado cancelado expirado }
enum EstadoPago { pendiente aprobado rechazado }
enum EstadoReembolso { pendiente completado fallido }
enum TipoItem { producto combo }
enum Rol { cliente administrador cajero despacho dueno }
enum EstadoEnvioComprobante { pendiente simulado fallido }

input FiltrosProductos {
  productoId: ID
  categoriaId: ID
  busqueda: String
  soloDisponibles: Boolean = false
  incluirInactivos: Boolean = false
}
input FiltrosCombos { comboId: ID busqueda: String soloDisponibles: Boolean = false }
input FiltrosCatalogo { productos: FiltrosProductos combos: FiltrosCombos }
input FiltrosPedidos { estado: EstadoPedido desde: String hasta: String }

type Query {
  catalogo(filtros: FiltrosCatalogo, pagina: Int! = 1, limite: Int! = 12): Catalogo
  perfil: PerfilUsuario
  misPedidos(filtros: FiltrosPedidos, pagina: Int! = 1, limite: Int! = 20): PaginaPedidos
  pedido(id: ID!): Pedido
  pedidos(filtros: FiltrosPedidos, pagina: Int! = 1, limite: Int! = 20): PaginaPedidos
  reporteVentas(desde: String!, hasta: String!, pagina: Int! = 1, limite: Int! = 20): ReporteVentas
}

type Paginacion { pagina: Int! limite: Int! total: Int! }
type Categoria { id: ID! nombre: String! }
type Catalogo { categorias: [Categoria!] productos: PaginaProductos combos: PaginaCombos }
type PaginaProductos { items: [Producto!]! paginacion: Paginacion! }
type PaginaCombos { items: [Combo!]! paginacion: Paginacion! }
type Producto {
  id: ID!
  nombre: String!
  descripcion: String
  categoria: Categoria!
  precio: Int!
  precioOferta: Int
  precioFinal: Int!
  disponible: Boolean!
  activo: Boolean!
  stock: Int
}
type ComponenteCombo { id: ID! nombre: String! cantidad: Int! }
type Combo {
  id: ID!
  nombre: String!
  descripcion: String
  precio: Int!
  precioOferta: Int
  precioFinal: Int!
  disponible: Boolean!
  productos: [ComponenteCombo!]!
}
type PerfilUsuario {
  id: ID!
  identificador: String!
  rol: Rol!
  clienteId: ID
  correoVerificado: Boolean
  datosCliente: DatosPerfil
}
type DatosPerfil {
  nombres: String!
  apellidos: String!
  rut: String!
  email: String!
  telefono: String
  direccion: String
  comuna: String
}
type PaginaPedidos { items: [ResumenPedido!]! paginacion: Paginacion! }
type ResumenPedido {
  id: ID!
  estado: EstadoPedido!
  creadoEn: String!
  pagadoEn: String
  moneda: String!
  total: Int
  ventaId: ID
  pago: ResumenPago
}
type Pedido {
  id: ID!
  estado: EstadoPedido!
  version: Int!
  creadoEn: String!
  actualizadoEn: String!
  pagadoEn: String
  venceEn: String
  moneda: String!
  subtotal: Int
  descuento: Int
  costoEnvio: Int
  total: Int
  ventaId: ID
  cliente: ClientePedido
  direccion: DireccionPedido
  lineas: [LineaPedido!]!
  historial(pagina: Int! = 1, limite: Int! = 20): PaginaHistorial
  pago: ResumenPago
  reembolso: ResumenReembolso
  comprobante: Comprobante
}
type ClientePedido { nombres: String! apellidos: String! telefono: String }
type DireccionPedido { calle: String! numero: String! departamento: String comuna: String! }
type LineaPedido {
  id: ID!
  tipo: TipoItem!
  referenciaId: ID!
  nombre: String!
  cantidad: Int!
  precioUnitario: Int
  subtotal: Int
  catalogoActual: ItemCatalogoActual
}
type ItemCatalogoActual { id: ID! nombre: String! precioFinal: Int! disponible: Boolean! }
type PaginaHistorial { items: [EventoPedido!]! paginacion: Paginacion! }
type EventoPedido { estado: EstadoPedido! fecha: String! }
type ResumenPago { id: ID! estado: EstadoPago! monto: Int! moneda: String! }
type ResumenReembolso {
  id: ID!
  estado: EstadoReembolso!
  montoDevuelto: Int!
  moneda: String!
  reintentable: Boolean!
}
type Comprobante { id: ID! ventaId: ID! numero: String! estadoEnvio: EstadoEnvioComprobante! }
type ReporteVentas {
  desde: String!
  hasta: String!
  zonaHoraria: String!
  moneda: String!
  cantidadVentas: Int
  ventas: PaginaVentas
  totalCobrado: Dinero
  totalDevuelto: Dinero
  netoCobrado: Dinero
}
type PaginaVentas { items: [VentaReporte!]! paginacion: Paginacion! }
type VentaReporte {
  id: ID!
  pedidoId: ID!
  fecha: String!
  estadoPedido: EstadoPedido!
  total: Int!
}
```

## Consultas y respuestas ficticias

Envoltorio HTTP: query contiene el documento GraphQL, operationName su nombre y variables el objeto indicado. Cliente propietario para G01/G02/G04, Despacho para el ejemplo G05 y Administrador/Dueño para G06. G03 es anónimo. Los 20000 devueltos del reporte corresponden a ventas anteriores: muestra por qué el neto puede ser negativo.

### G03 · VerCatalogo

```graphql
query VerCatalogo($filtros: FiltrosCatalogo, $pagina: Int, $limite: Int) {
  catalogo(filtros: $filtros, pagina: $pagina, limite: $limite) {
    categorias { id nombre }
    productos {
      items { id nombre categoria { id nombre } precio precioOferta precioFinal disponible }
      paginacion { pagina limite total }
    }
    combos { items { id nombre disponible productos { id nombre cantidad } } paginacion { pagina limite total } }
  }
}
```

Variables:

```json
{
  "filtros": {
    "productos": {
      "categoriaId": "1"
    }
  },
  "pagina": 1,
  "limite": 12
}
```

Respuesta ficticia:

```json
{
  "data": {
    "catalogo": {
      "categorias": [
        {
          "id": "1",
          "nombre": "Bowls"
        }
      ],
      "productos": {
        "items": [
          {
            "id": "1",
            "nombre": "Bowl Proteico Demo",
            "categoria": {
              "id": "1",
              "nombre": "Bowls"
            },
            "precio": 6500,
            "precioOferta": null,
            "precioFinal": 6500,
            "disponible": true
          }
        ],
        "paginacion": {
          "pagina": 1,
          "limite": 12,
          "total": 1
        }
      },
      "combos": {
        "items": [],
        "paginacion": {
          "pagina": 1,
          "limite": 12,
          "total": 0
        }
      }
    }
  }
}
```

### G02 · VerPedido

```graphql
query VerPedido($id: ID!) {
  pedido(id: $id) {
    id estado version venceEn moneda subtotal descuento costoEnvio total
    lineas { id tipo referenciaId nombre cantidad precioUnitario subtotal catalogoActual { id nombre precioFinal disponible } }
    pago { id estado monto moneda }
    reembolso { id estado montoDevuelto moneda reintentable }
  }
}
```

Variables:

```json
{
  "id": "101"
}
```

Respuesta ficticia:

```json
{
  "data": {
    "pedido": {
      "id": "101",
      "estado": "pagado",
      "version": 2,
      "venceEn": "2026-10-24T14:15:00Z",
      "moneda": "CLP",
      "subtotal": 13000,
      "descuento": 0,
      "costoEnvio": 1500,
      "total": 14500,
      "lineas": [
        {
          "id": "501",
          "tipo": "producto",
          "referenciaId": "1",
          "nombre": "Bowl Proteico Demo",
          "cantidad": 2,
          "precioUnitario": 6500,
          "subtotal": 13000,
          "catalogoActual": {
            "id": "1",
            "nombre": "Bowl Proteico Demo",
            "precioFinal": 7000,
            "disponible": true
          }
        }
      ],
      "pago": {
        "id": "201",
        "estado": "aprobado",
        "monto": 14500,
        "moneda": "CLP"
      },
      "reembolso": null
    }
  }
}
```

### G04 · MiPerfil

```graphql
query MiPerfil {
  perfil { id rol clienteId correoVerificado datosCliente { nombres apellidos email telefono direccion comuna } }
}
```

Variables:

```json
{}
```

Respuesta ficticia:

```json
{
  "data": {
    "perfil": {
      "id": "10",
      "rol": "cliente",
      "clienteId": "7",
      "correoVerificado": true,
      "datosCliente": {
        "nombres": "Cliente",
        "apellidos": "Demo",
        "email": "cliente@example.com",
        "telefono": null,
        "direccion": "Calle Demo 100",
        "comuna": "Comuna Demo"
      }
    }
  }
}
```

### G01 · MiHistorial

```graphql
query MiHistorial($filtros: FiltrosPedidos) {
  misPedidos(filtros: $filtros) {
    items { id estado creadoEn total moneda pago { id estado monto moneda } }
    paginacion { pagina limite total }
  }
}
```

Variables:

```json
{
  "filtros": {
    "estado": "pagado"
  }
}
```

Respuesta ficticia:

```json
{
  "data": {
    "misPedidos": {
      "items": [
        {
          "id": "101",
          "estado": "pagado",
          "creadoEn": "2026-10-24T14:00:00Z",
          "total": 14500,
          "moneda": "CLP",
          "pago": {
            "id": "201",
            "estado": "aprobado",
            "monto": 14500,
            "moneda": "CLP"
          }
        }
      ],
      "paginacion": {
        "pagina": 1,
        "limite": 20,
        "total": 1
      }
    }
  }
}
```

### G05 · ColaPreparacion

```graphql
query ColaPreparacion {
  pedidos(filtros: {estado: pagado}) {
    items { id estado creadoEn pagadoEn }
    paginacion { pagina limite total }
  }
}
```

Variables:

```json
{}
```

Respuesta ficticia:

```json
{
  "data": {
    "pedidos": {
      "items": [
        {
          "id": "101",
          "estado": "pagado",
          "creadoEn": "2026-10-24T14:00:00Z",
          "pagadoEn": "2026-10-24T14:04:00Z"
        }
      ],
      "paginacion": {
        "pagina": 1,
        "limite": 20,
        "total": 1
      }
    }
  }
}
```

### G06 · ReportePeriodo

```graphql
query ReportePeriodo($desde: String!, $hasta: String!) {
  reporteVentas(desde: $desde, hasta: $hasta) {
    desde hasta zonaHoraria moneda cantidadVentas totalCobrado totalDevuelto netoCobrado
    ventas { items { id pedidoId fecha estadoPedido total } paginacion { pagina limite total } }
  }
}
```

Variables:

```json
{
  "desde": "2026-10-24",
  "hasta": "2026-10-24"
}
```

Respuesta ficticia:

```json
{
  "data": {
    "reporteVentas": {
      "desde": "2026-10-24",
      "hasta": "2026-10-24",
      "zonaHoraria": "America/Santiago",
      "moneda": "CLP",
      "cantidadVentas": 1,
      "totalCobrado": "14500",
      "totalDevuelto": "20000",
      "netoCobrado": "-5500",
      "ventas": {
        "items": [
          {
            "id": "301",
            "pedidoId": "101",
            "fecha": "2026-10-24T14:04:00Z",
            "estadoPedido": "pagado",
            "total": 14500
          }
        ],
        "paginacion": {
          "pagina": 1,
          "limite": 20,
          "total": 1
        }
      }
    }
  }
}
```

## Límites y errores

El schema puede explorarse mediante introspección estándar para aprender y probar las consultas; se mantienen los límites y la autorización de datos por recurso/campo.

- Profundidad: 6 niveles contando campos desde la raíz. Costo: máximo 2000; un campo escalar vale 1 y los objetos suman sus selecciones; una lista multiplica por su cardinalidad máxima validada. Se cuentan aliases y cada aparición efectiva; no se evita el límite mediante fragments o variables.
- Paginadas usan limite, máximo 50. Referencias técnicas iniciales para listas no paginadas: hasta 50 categorías, 20 componentes por combo y 50 líneas por checkout. Validar seeds/legacy antes de aplicar esos topes; nunca truncar una compra histórica. Si una lista excede el contrato debe migrarse/paginarse, no ocultar datos. Son límites auxiliares de diseño, revisables con evidencia.
- Plazo global 10 s; cada llamada privada hasta 3 s, dentro de una ejecución máxima de 10 s. El gateway externo deja 15 s para la ruta GraphQL, para permitir respuesta controlada del agregador. Cuerpo HTTP máximo inicial 64 KiB; lotes I04/I16 de hasta 50 referencias por llamada, sin una llamada por línea y dentro del costo/plazo global.
- Frecuencia externa: 60 solicitudes/min por usuario; 120/min por IP anónima. Contadores en memoria por minuto fijo; login REST se bloquea después de cinco fallos en ese minuto/IP. 429 con Retry-After; llamadas privadas no consumen otra vez el cupo externo.
- No hay caché compartida de identidad, ofertas o datos de pedidos entre usuarios. Se agrupan referencias por página/pedido; no hay un gestor de caché por solicitud.

| Código de Fit Express | Comportamiento |
| --- | --- |
| ENTRADA_INVALIDA | ID, fechas, filtros o página/límite inválidos. |
| NO_AUTENTICADO | Campo/operación requiere sesión válida. |
| PROHIBIDO | Rol/caja/finalidad/campo fuera de alcance. |
| NO_ENCONTRADO | Recurso inexistente o ajeno, sin filtrar propietario. |
| CONSULTA_EXCESIVA | Profundidad/costo excedidos; rechazar antes de enriquecer. |
| DEPENDENCIA_NO_DISPONIBLE | Campo requerido de una dependencia no pudo obtenerse. |
| TIEMPO_AGOTADO | Plazo máximo de consulta/campo agotado. |

Son códigos propios en errors[].extensions.code. Cada error de campo incluye path y mensaje controlado. Error de sintaxis/tipos/estructura: HTTP 400 antes de resolvers. Ejecución válida con errores por campo puede responder HTTP 200 con data parcial y errors. Un rechazo de frecuencia/cuerpo del gateway usa 429/413 antes de GraphQL. Una sesión presentada pero inválida se rechaza; no se transforma en identidad de Cliente ni conserva ofertas.

El helper frontend debe tratar tanto data como errors, incluso con HTTP exitoso. Caída de inventory no significa agotado ni borra líneas; caída de payments no significa pago rechazado o cero devuelto. Ausencia real de intento/devolución o artículo retirado produce null sin error; no se confunde con fallo de dependencia.

## Estado y siguiente implementación

Primero catalogo y pedido; luego perfil, misPedidos, pedidos y reporteVentas. Implementar contratos privados, snapshots, sesión/roles y resolvers sin acceso a bases ajenas; migrar consumidores y después retirar las ocho lecturas REST públicas de la lista del gateway. Todavía faltan pruebas de ejecución, fallos/concurrencia, carga, matrices de trazabilidad y UML. El schema de documentación no completa por sí solo M1/M6/M8.

Referencias: [queries y argumentos](https://graphql.org/learn/queries/), [schema y nullabilidad](https://graphql.org/learn/schema/) y [respuestas parciales](https://graphql.org/learn/response/). Los valores numéricos y reglas funcionales son decisiones de Fit Express, no límites universales de GraphQL.
