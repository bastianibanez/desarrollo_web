# Contratos GraphQL

El gateway publica `POST /api/graphql` y reenvía al servidor privado Apollo. El frontend estático no hace estas consultas.

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
- Público recibe únicamente disponible, sin cantidades exactas. `stock` y `incluirInactivos` están restringidos a Administrador/Dueño. Seleccionarlos sin permiso produce FORBIDDEN; un parámetro privilegiado no se ignora silenciosamente. Activo es un indicador, sin agregar una operación de reactivación a este alcance.
- Retirados fuera del catálogo público. Orders conserva compras anteriores. Las imágenes siguen en frontend/src/imagenes.js; no se añade gestión de archivos.
- Se puede solicitar una página nueva únicamente de productos sin volver a solicitar combos. Los carruseles deben paginar por categoría, no asumir que los primeros 12 productos representan todas las categorías.

## Pedido, dinero y datos históricos

Orders conserva nombre/precio de las líneas, dirección/contacto necesarios de esa compra, tarifa, moneda, vencimiento, caja/cajero y fechas. El backend nuevo implementa snapshots, listado/historial, versionado y estados; el backend histórico se conserva sin migrar. Estos datos no se completan leyendo el perfil o catálogo actuales por JOIN.

`subtotal` es la suma de cantidad por precio unitario aceptado, incluidas las ofertas aplicadas; `descuento` solo representa otro descuento del pedido, actualmente cero. `total = subtotal - descuento + costoEnvio`. El envío proviene de la tarifa oficial por comuna; no se impone costo cero ni distancia. Los datos de catalogoActual son actuales y opcionales, nunca reemplazan la compra histórica.

`venceEn` conserva el vencimiento original; el contador solo se muestra en pendiente. `estado` usa los siete valores canónicos del schema. La base histórica no se migra automáticamente. La devolución es independiente: un pedido puede ser entregado con reembolso completado.

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

Campos restringidos nullable devuelven null con FORBIDDEN. Inexistente/ajeno para Cliente: mismo NOT_FOUND y pedido null. Los resolvers cargan los enriquecimientos autorizados al resolver la página o pedido; GraphQL solo devuelve los campos solicitados. No hay optimización por selección de campos ni caché de tareas. I04 agrupa referencias tipo+ID; I16 agrupa pedidos y reutiliza su respuesta para pago/reembolso dentro de la misma operación.

## Reporte y fechas

Listado/cantidad corresponden a ventas registradas en orders durante el período. Total cobrado/devuelto/neto corresponden a movimientos verificados de payments por su propia fecha; un cobro tardío sin venta válida también es un movimiento financiero. Por eso no se exige igualdad entre suma de filas y totalCobrado del período.

Una venta del lunes devuelta el martes conserva el cobro en lunes y la devolución en martes. Neto puede ser negativo. Payments calcula neto como cobrado menos devuelto una sola vez. Si falta I17, los tres indicadores son null con error, no cero; un consumidor debe indicar reporte incompleto. Orders y payments pueden devolver sus partes autorizadas independientemente. No hay rankings ni desglose diario/por producto.

## Límites y errores

El schema puede explorarse mediante introspección estándar para aprender y probar las consultas; se mantienen los límites y la autorización de datos por recurso/campo.

- Profundidad: 6 niveles contando campos desde la raíz. Costo: máximo 2000; un campo escalar vale 1 y los objetos suman sus selecciones; una lista multiplica por su cardinalidad máxima validada. Se cuentan aliases y cada aparición efectiva; no se evita el límite mediante fragments o variables.
- Paginadas usan limite, máximo 50. Referencias técnicas iniciales para listas no paginadas: hasta 50 categorías, 20 componentes por combo y 50 líneas por checkout. Validar seeds/legacy antes de aplicar esos topes; nunca truncar una compra histórica. Si una lista excede el contrato debe migrarse/paginarse, no ocultar datos. Son límites auxiliares de diseño, revisables con evidencia.
- Plazo global 10 s; cada llamada privada hasta 3 s, dentro de una ejecución máxima de 10 s. El gateway externo deja 15 s para la ruta GraphQL, para permitir respuesta controlada del agregador. Cuerpo HTTP máximo inicial 64 KiB; lotes I04/I16 de hasta 50 referencias por llamada, sin una llamada por línea y dentro del costo/plazo global.
- Frecuencia externa: 60 solicitudes/min por usuario; 120/min por IP anónima. Contadores en memoria por minuto fijo; login REST se bloquea después de cinco fallos en ese minuto/IP. 429 con Retry-After; llamadas privadas no consumen otra vez el cupo externo.
- No hay caché compartida de identidad, ofertas o datos de pedidos entre usuarios. Se agrupan referencias por página/pedido; no hay un gestor de caché por solicitud.

| Código de Fit Express | Comportamiento |
| --- | --- |
| BAD_USER_INPUT | ID, fechas, filtros o página/límite inválidos. |
| UNAUTHENTICATED | Campo/operación requiere sesión válida. |
| FORBIDDEN | Rol/caja/finalidad/campo fuera de alcance. |
| NOT_FOUND | Recurso inexistente o ajeno, sin filtrar propietario. |
| QUERY_LIMIT | Profundidad/costo excedidos; rechazar antes de enriquecer. |
| DEPENDENCY_UNAVAILABLE | Campo requerido de una dependencia no pudo obtenerse. |
| TIMEOUT | Plazo máximo de consulta/campo agotado. |

Son códigos propios en errors[].extensions.code. Cada error de campo incluye path y mensaje controlado. Error de sintaxis/tipos/estructura: HTTP 400 antes de resolvers. Ejecución válida con errores por campo puede responder HTTP 200 con data parcial y errors. Un rechazo de frecuencia/cuerpo del gateway usa 429/413 antes de GraphQL. Una sesión presentada pero inválida se rechaza; no se transforma en identidad de Cliente ni conserva ofertas.

Un consumidor de esta API debe tratar tanto data como errors, incluso con HTTP exitoso; la demo actual no la consume. Caída de inventory no significa agotado ni borra líneas; caída de payments no significa pago rechazado o cero devuelto. Ausencia real de intento/devolución o artículo retirado produce null sin error; no se confunde con fallo de dependencia.

## Schema y resolvers

Referencias ejecutables: [schema.graphql](../services/graphql/schema.graphql), [resolvers.js](../services/graphql/resolvers.js), [context.js](../services/graphql/context.js) y [limits.js](../services/graphql/limits.js). Se evita mantener una segunda copia del schema en este documento.

## Ejemplos de consulta

Catálogo público:

```graphql
{ catalogo(limite: 12) { productos { items { id nombre precioFinal disponible } } } }
```

Pedido propio, con Bearer:

```graphql
query Pedido($id: ID!) {
  pedido(id: $id) {
    id estado total
    pago { estado }
    comprobante { numero }
    lineas { nombre cantidad }
  }
}
```

Reporte autorizado, con datos de orders y payments:

```graphql
{
  reporteVentas(desde: "2026-11-01", hasta: "2026-11-09") {
    cantidadVentas totalCobrado totalDevuelto netoCobrado
    ventas { items { id total } }
  }
}
```

Las respuestas usan `data` y, cuando corresponde, `errors`. Los campos financieros requieren permisos adicionales: un error de campo no debe conceder acceso ni eliminar los datos históricos accesibles. Ver las pruebas de permisos, fallos parciales y límites en [test_backend.py](../services/tests/test_backend.py).
