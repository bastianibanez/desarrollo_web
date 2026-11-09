# Modelo de datos y cardinalidades

Cada servicio tiene su propia base SQLite. Las FK son locales; las relaciones entre servicios son referencias verificadas por API. El esquema físico vigente está en los archivos `services/*/schema.sql`.

| Servicio | Fuente del esquema | Responsabilidad |
| --- | --- | --- |
| auth | [schema.sql](../services/auth/schema.sql) | Sesiones y versión de cuenta. |
| clients | [schema.sql](../services/clients/schema.sql) | Perfiles, cuentas y hashes de contraseñas. |
| inventory | [schema.sql](../services/inventory/schema.sql) | Catálogo, combos, stock y reservas. |
| orders | [schema.sql](../services/orders/schema.sql) | Pedidos, snapshots, caja, ventas y comprobantes. |
| payments | [schema.sql](../services/payments/schema.sql) | Intentos de pago, solicitudes y reembolsos. |
| simulator | [schema.sql](../services/simulator/schema.sql) | Estado separado del proveedor ficticio. |

## Relaciones y cardinalidades

Cada fila indica cuántos destinos puede tener **un origen** y a cuántos orígenes pertenece **un destino**. FK son asociaciones locales; REF son relaciones del negocio entre servicios, no claves foráneas distribuidas.

| Origen → destino | Destinos por origen | Orígenes por destino | Tipo y justificación |
| --- | --- | --- | --- |
| Cliente → Usuario | 0..1 | 0..1 | FK UNIQUE: registro sin acceso aún; funcionario sin Cliente. Usuario con rol cliente exige exactamente un Cliente. |
| Usuario → Sesion | 0..* | 1 | REF clients → auth: varios accesos, cada sesión de una cuenta; sin FK entre bases. |
| Categoria → Producto | 0..* | 1 | FK: producto siempre categorizado. |
| Combo → LineaCombo | 1..* | 1 | FK: combo válido no vacío. |
| Producto → LineaCombo | 0..* | 1 | FK: receta puede reutilizar productos. |
| ReservaStock → LineaReserva | 1..* | 1 | FK: cotización no vacía. |
| ReservaStock → DetalleReserva | 1..* | 1 | FK: toda reserva compromete unidades. |
| Producto → DetalleReserva | 0..* | 1 | FK: misma existencia puede participar en reservas distintas. |
| Producto → LineaReserva | 0..* | 0..1 | FK: solo líneas de producto; XOR con Combo. |
| Combo → LineaReserva | 0..* | 0..1 | FK: solo líneas de combo; XOR con Producto. |
| Comuna → TarifaEnvio | 0..1 | 1 | FK UNIQUE: exige tarifa para despacho habilitado. |
| Comuna → Pedido | 0..* | 1 | FK: referencia local más copia histórica del nombre. |
| Comuna → Cliente | 0..* | 0..1 | REF: dirección actual del perfil, sin FK entre bases; admite registros anteriores incompletos. |
| Caja → Pedido | 0..* | 1 | FK: caja aceptada para cada compra. |
| Cliente → Pedido | 0..* | 1 | REF: propietario validado por clients. |
| Pedido → ReservaStock | 1 | 0..1 | REF: checkout completado tiene reserva única; reserva puede existir antes de que el pedido termine de persistirse. |
| Pedido → LineaPedido | 1..* | 1 | FK: compra completada no vacía. |
| Producto/Combo → LineaPedido | 0..* | 0..1 de cada tipo | REF: exactamente uno de los dos tipos por línea; el snapshot permanece. |
| Pedido → EventoPedido | 1..* | 1 | FK: creación y evolución auditables. |
| Pedido → Venta | 0..1 | 1 | FK UNIQUE: pedidos impagos no son ventas. |
| Caja → Venta | 0..* | 1 | FK: asociación comercial histórica. |
| Usuario cajero → Caja | 0..1 | 0..1 | REF: una única caja Web configurable; puede no estar asignada todavía. |
| Usuario cajero → Pedido/Venta | 0..* | 1 | REF: identidad histórica, sin FK a clients. |
| Venta → Comprobante | 0..1 | 1 | FK UNIQUE: emisión puede fallar/reintentarse antes de existir el documento. |
| Pedido → IntentoPago | 0..* | 1 | REF: rechazos y reintentos, incluso cobros tardíos. |
| Pedido → IntentoPago aceptado | 0..1 | 0..1 | REF UNIQUE: pago_confirmado_id, distinto de la colección de todos los intentos. |
| IntentoPago → Venta | 0..1 | 1 | REF UNIQUE: cobro aceptado crea venta; duplicados/tardíos no. |
| IntentoPago → EventoProveedor | 0..* | 0..1 | La referencia de transacción enlaza los avisos de pago. |
| IntentoPago → SolicitudReembolso | 0..* | 1 | FK: rechazadas conservadas; una pendiente/aprobada por pedido. |
| SolicitudReembolso → Reembolso | 0..1 | 0..1 | FK UNIQUE: rechazadas sin devolución; causas técnicas sin solicitud. |
| IntentoPago → Reembolso | 0..1 | 1 | FK UNIQUE: un proceso por cobro íntegro. |
| Reembolso → IntentoReembolso | 0..* | 1 | FK: puede estar creado antes del primer contacto con proveedor; se conservan todos los intentos. |

Para las cabeceras aún en coordinación, los mínimos de Pedido son invariantes al **completar checkout**, no promesas de una transacción SQL entre bases. Las etapas se conservan en registros técnicos; no se expone un pedido comprable sin reserva/ítems.

## Comprobación del diseño con escenarios

| Escenario | Datos que lo hacen posible |
| --- | --- |
| Última unidad entre dos checkouts | Reserva y detalles transaccionales; stock libre comprobado antes de confirmar. |
| Producto suelto y combos usan el mismo snack | DetalleReserva agregado, sin stock independiente de combos. |
| Se pierde la respuesta de I05 | operacion_checkout única, líneas cotizadas persistidas y operación recuperable. |
| Precio/contacto/tarifa cambia tras comprar | Snapshots de Pedido y LineaPedido. |
| Pago rechazado y segundo intento aprobado | Varios IntentoPago, una Venta y un Comprobante. |
| Aviso duplicado o cobro sobrante | EventoProveedor único; pago aceptado único en orders; reembolso por cada cobro sobrante. |
| Pago después del vencimiento | Reserva terminal, pedido expirado/cancelado y devolución en payments; sin nueva venta. |
| Cancelar y preparar a la vez | Versión del Pedido, transición/historial local atómicos y reintento explícito de las operaciones de stock/devolución. |
| Excepción durante preparación o envío | Causa y decisión persistidas; cancelación solo si preparando; devolución sin restitución. |
| Fallo/resultado incierto de devolución | Reembolso estable e IntentoReembolso histórico; consultar antes de generar otro intento. |
| Cambia el cajero de la Web | Pedido/Venta conservan cajero previo; Caja refleja asignación actual. |
| Cobro lunes y devolución martes | aprobado_en/completado_en verificados; reporte por movimiento, neto del martes puede ser negativo. |

[UML de dominio editable](modelo-dominio.mmd) · [SVG](modelo-dominio.svg) · [UML de servicios](diagramas/dominio-servicios.mmd). Auth almacena las sesiones; Usuario pertenece a clients, sin FK distribuida.
