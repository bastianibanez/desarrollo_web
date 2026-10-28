# Fit Express

Fit Express vende bowls proteicos, snacks y combos por la web, con entrega en comunas habilitadas. Este glosario distingue los conceptos que intervienen en una compra y su eventual devolución.

## Lenguaje

**Cliente**:
Persona registrada cuyos datos de contacto y entrega se utilizan para sus compras.
_Evitar_: Usuario como sinónimo del perfil comercial.

**Usuario**:
Cuenta de acceso con credenciales y un rol; puede corresponder a un cliente o a un funcionario.
_Evitar_: Cliente como sinónimo de cualquier cuenta.

**Carrito**:
Selección modificable de productos y combos antes de confirmar la compra; todavía no compromete existencias.
_Evitar_: Pedido pendiente para referirse a una selección sin confirmar.

**Pedido**:
Compra confirmada en checkout, con sus ítems, precios y entrega aceptados, que recorre un ciclo operativo.
_Evitar_: Carrito, pago o venta como sinónimos. «Orden» se conserva como nombre equivalente en las rutas existentes.

**Reserva de stock**:
Compromiso temporal de unidades para un checkout, que puede consumirse, liberarse o vencer.
_Evitar_: Descuento definitivo de stock para referirse a una reserva activa.

**Liberación**:
Fin de un compromiso de unidades que todavía no se habían consumido.
_Evitar_: Restitución para una reserva sin consumo.

**Restitución**:
Devolución al stock de unidades ya consumidas, cuando procede una cancelación normal antes de preparar.
_Evitar_: Liberación, reembolso.

**Intento de pago**:
Operación de cobro con resultado verificado propio; un pedido puede tener varios intentos y un rechazo no constituye una venta.
_Evitar_: Pedido pagado como sinónimo de cualquier intento aprobado, porque un cobro tardío puede requerir devolución.

**Venta**:
Registro único de un pedido aceptado como pagado, asociado a su caja y cajero históricos.
_Evitar_: Intento de pago, comprobante.

**Comprobante**:
Documento único de una venta confirmada; su emisión y su envío tienen resultados distintos.
_Evitar_: Confirmación del proveedor como sinónimo del documento de la venta.

**Cancelación normal**:
Interrupción del pedido antes de preparar, con liberación o restitución de unidades y devolución del dinero cuando corresponda.
_Evitar_: Eliminación del pedido.

**Solicitud excepcional de reembolso**:
Petición textual del cliente desde la preparación, que requiere una decisión administrativa.
_Evitar_: Reembolso ejecutado como sinónimo de solicitud aprobada.

**Reembolso**:
Proceso de devolución del saldo pagado de un cobro, con causa y resultado financiero propios.
_Evitar_: Estado del pedido; devolver dinero no implica siempre detener la entrega ni restituir stock.
