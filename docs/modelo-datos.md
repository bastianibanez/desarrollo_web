# Modelo de datos de Fit Express

**Actualización del 28 de octubre:** el esquema físico inicial de los cuatro servicios está en [schema de clients](../services/clients/schema.sql) y [schema de Auth](../services/auth/schema.sql), con bases separadas y pruebas nuevas. Este documento conserva el diseño lógico de referencia; [estado-backend-e2.md](estado-backend-e2.md) distingue lo ejecutado de las verificaciones pendientes. No se migró ni alteró la base histórica.

Propuesta de diseño lógico al 24 de octubre de 2026, derivada de [las reglas acordadas](reglas-pedidos.md), [los contratos REST](contratos-rest.md), [GraphQL](contratos-graphql.md) y el esquema actual de `backend_api/db.py`. No crea tablas ni modifica la aplicación. Las decisiones de estructura propuestas aquí se pueden ajustar al implementar, conservando las reglas de negocio.

**Cambio de separación:** Auth almacena sesiones; clients conserva cuentas y hashes. `sesiones` en Auth usa `token_hash`, `usuario_id` como referencia remota, `version_cuenta`, `creado_en` y `expira_at`. No existe FK entre bases. Las sesiones antiguas de clients no se migran; sus tablas históricas se conservan sin uso. El diagrama anterior requiere ajustar esta separación al preparar el UML final.

Vocabulario: [CONTEXT.md](../CONTEXT.md). Diagrama de clases del dominio editable: [modelo-dominio.mmd](modelo-dominio.mmd), con [exportación SVG ampliable](modelo-dominio.svg). El diagrama muestra asociaciones del dominio con multiplicidades en ambos extremos; las etiquetas REF indican relaciones entre servicios, no FK SQL ni flujos de red. El rombo representa composición y no implica borrado en cascada del historial. Se agrupan algunos atributos de snapshot para legibilidad; las columnas y nulabilidad se especifican en este documento. El UML de servicios/DTO y el UML de gateway/políticas se completarán por separado; este modelo no acredita todo el módulo 2 de la evaluación.

## 1. Distribución y convenciones

| Servicio | Entidades/tablas de la propuesta | Autoridad |
| --- | --- | --- |
| clients | Cliente/clientes, Usuario/usuarios | Perfil, credenciales, rol y verificación. |
| auth | Sesion/sesiones | Tokens personales y validación de acceso; cuenta consultada en clients por API privada. |
| inventory | Categoria/categorias, Producto/productos, Combo/combos, LineaCombo/lineas_combo, ReservaStock/reservas, LineaReserva/lineas_reserva, DetalleReserva/detalles_reserva | Catálogo, precios, unidades físicas y compromisos. |
| orders | Comuna/comunas, TarifaEnvio/costos_envio, Caja/cajas, Pedido/ordenes, LineaPedido/lineas_orden, EventoPedido/eventos_pedido, Venta/ventas, Comprobante/comprobantes | Cobertura/tarifas, compra, recorrido operativo y documentación de venta. |
| payments | IntentoPago/pagos, EventoProveedor/eventos_proveedor, SolicitudReembolso/solicitudes_reembolso, Reembolso/reembolsos, IntentoReembolso/intentos_reembolso | Resultados financieros verificados y devoluciones. |

Son **23 tablas principales**. Se conserva `ordenes` en SQL y `/ordenes` en REST para facilitar la migración; en el dominio y GraphQL se habla de Pedido. Las entidades nuevas responden a reservas, trazabilidad y pagos: no implican nuevos mantenedores o pantallas fuera del alcance acordado.

- Un archivo SQLite privado por servicio: `clients.db`, `inventory.db`, `orders.db` y `payments.db`, con volumen persistente. Es una propuesta de despliegue; todavía no existen esas bases separadas.
- **FK**: clave foránea dentro de la misma base, con `PRAGMA foreign_keys = ON` en cada conexión. **REF**: ID de otro servicio, validado mediante su API; no lleva FK SQL ni permite consultar su base.
- ID interno: entero positivo. Cantidades e importes: enteros; dinero CLP sin decimales, nunca `float`. Importes individuales compatibles con el `Int` de los contratos; acumulados calculados y expuestos como cadena decimal cuando corresponde.
- Texto `?` o tipo `?`: admite `NULL`. Booleanos SQLite: 0/1 con restricción. Fechas: texto ISO 8601 UTC; nacimiento: `YYYY-MM-DD`. La consulta por días aplica `America/Santiago`.
- Todas las entidades mutables llevan `creado_en` y `actualizado_en`, salvo que se indique otra cosa. Los nombres actuales `created_at`/`updated_at` pueden conservarse en SQL mediante un mapeo explícito; no hace falta renombrarlos para que el modelo sea válido.
- Los estados cerrados usan `CHECK` y validación del servicio. Los historiales son aditivos; no hay borrado en cascada del historial comercial.
- API Gateway, GraphQL y Vault no tienen tablas de clientes/pedidos propias. Vault custodia secretos de integración; las contraseñas de usuario se verifican con hashes en clients.

## 2. clients

### Cliente → clientes

| Campos | Tipos y restricciones |
| --- | --- |
| id, nombres, apellidos, rut, email | ID PK; textos requeridos; RUT y email normalizados y únicos. |
| telefono, direccion, comuna_id, comuna_nombre, provincia, region, fecha_nacimiento, sexo | Texto, salvo comuna_id REF a orders y nacimiento fecha. Conservar los campos del registro actual; su obligatoriedad sigue los DTO. `comuna_nombre` es una copia para el perfil. |
| activo, email_verificado_en | Booleano; fecha nullable. |
| codigo_hash, codigo_expira_en, intentos_codigo | Texto/fecha nullables y entero >= 0. Nunca guardar o devolver el código en claro. |

La dirección del perfil es un valor actual editable; la dirección de un pedido es una copia histórica distinta. Cambio de email invalida la verificación anterior y las sesiones afectadas, según el contrato. El código dura 15 minutos y admite cinco fallos; se mantiene en Cliente para conservar el flujo actual sin una tabla adicional.

### Usuario → usuarios

| Campos | Tipos y restricciones |
| --- | --- |
| id, cliente_id | ID PK; cliente_id FK nullable y UNIQUE. |
| identificador, password_hash | Texto; identificador normalizado UNIQUE; hash requerido para una cuenta con acceso habilitado. |
| rol, activo | Enum cliente/administrador/cajero/despacho/dueno; booleano. |

Una cuenta tiene un solo rol en el alcance actual. Rol cliente exige cliente_id; los funcionarios no tienen perfil de Cliente. Un Cliente registrado puede no tener cuenta habilitada hasta verificar su correo y definir contraseña. Mantener un rol como enum evita tablas de roles/permisos que no requieren administración dinámica.

### Sesion → auth.sesiones

`token_hash: texto PK`, `usuario_id: ID REF a clients`, `version_cuenta: texto`, `creado_en: fecha`, `expira_at: fecha`.

Una cuenta tiene cero o muchas sesiones. `expira_en = creado_en + 8 horas`; no se desplaza con actividad. Logout o cambios que invalidan acceso marcan revocación o eliminan el registro de sesión; Auth comprueba también cuenta y rol actuales. Solo el token opaco personal llega al navegador; la base guarda su hash.

## 3. inventory

### Categoria → categorias

`id: ID PK`, `nombre: texto UNIQUE`.

Cada producto pertenece a una categoría; una categoría puede estar vacía. Categorías preconfiguradas, sin CRUD nuevo.

### Producto → productos

`id: ID PK`, `categoria_id: ID FK`, `nombre: texto`, `descripcion: texto?`, `precio: entero >= 0`, `precio_oferta: entero?`, `stock: entero >= 0`, `activo: booleano`.

La oferta, si existe, es >= 0 y menor al precio normal. `stock` significa unidades físicas todavía no consumidas, incluidas las comprometidas por reservas activas. La desactivación no borra el producto ni invalida reservas ya aceptadas.

### Combo → combos

`id: ID PK`, `nombre: texto`, `descripcion: texto?`, `precio: entero >= 0`, `precio_oferta: entero?`.

Sin stock propio: se calcula con sus componentes. La disponibilidad requiere componentes activos y unidades libres suficientes. Los combos quedan en seeds, sin CRUD nuevo; no se añade una categoría propia de combos.

### LineaCombo → lineas_combo

`id: ID PK`, `combo_id: ID FK`, `producto_id: ID FK`, `cantidad: entero > 0`; `UNIQUE(combo_id, producto_id)`.

Un combo válido tiene uno o más componentes; un producto puede formar parte de cero o muchos combos. El servicio/seeds validan el mínimo de componentes, que una FK por sí sola no garantiza.

### ReservaStock → reservas

`id: ID PK`, `operacion_checkout: texto UNIQUE`, `pedido_id: ID REF UNIQUE?`, `estado: enum`, `vence_en: fecha`, `consumida_en: fecha?`, `liberada_en: fecha?`, `restituida_en: fecha?`, `version: entero >= 1`.

Estados: activa, consumida, liberada, expirada, restituida. Vence 15 minutos después de crearse; repetir el checkout no modifica ese plazo. `pedido_id` puede faltar durante la coordinación inicial: I05 reserva por referencia de checkout antes de que orders termine de guardar el pedido. La reserva sobrevive a una respuesta perdida y se recupera con la misma referencia.

### LineaReserva → lineas_reserva

`id: ID PK`, `reserva_id: ID FK`, `posicion: entero > 0`, `producto_id: ID FK?`, `combo_id: ID FK?`, `nombre: texto`, `cantidad: entero > 0`, `precio_unitario: entero >= 0`.

Exactamente uno de producto_id/ combo_id; posición única dentro de la reserva. Son los ítems comerciales y precios aceptados en I05, guardados para que un reintento recupere la misma cotización aunque luego cambie el catálogo. `subtotal_linea = cantidad × precio_unitario` se calcula.

### DetalleReserva → detalles_reserva

`id: ID PK`, `reserva_id: ID FK`, `producto_id: ID FK`, `cantidad: entero > 0`; `UNIQUE(reserva_id, producto_id)`.

Son las unidades físicas agregadas por producto, incluyendo productos sueltos y todos los componentes de combos. No se calculan nuevamente con la receta actual al consumir o restituir. Una reserva tiene una o más líneas comerciales y uno o más detalles de unidades.

**Ejemplo:** 2 combos con 1 bowl y 2 snacks cada uno, más 1 snack suelto, producen 2 líneas comerciales y estos detalles: bowl=2, snack=5. Restaurar esa reserva devuelve esas mismas cantidades aunque el catálogo cambie.

### Regla de stock

`reservado(producto) = SUM(detalles de reservas activas con vence_en > ahora)`.

`disponible(producto) = stock − reservado(producto)`.

La reserva cambia compromisos, no el stock físico; consumir resta cantidades físicas y marca consumida en una transacción local. Liberar/expirar no suma stock. Restituir suma exactamente las cantidades consumidas y marca restituida una vez. No se almacena además `disponible` ni `stock_reservado` como otro contador que pueda divergir.

Comprobar disponibilidad y crear toda la reserva son una única operación local atómica en inventory. Consumo, vencimiento y edición de stock vuelven a comprobar estado/plazo en la transacción; una reserva vencida no se consume aunque su limpieza aún no corra. Reservas que comparten productos se suman antes de aceptar, evitando sobreventa por combos.

## 4. orders

### Comuna → comunas

`id: ID PK`, `nombre: texto`, `ciudad: texto`, `region: texto`, `habilitada: booleano`.

Se conservan los IDs y nombres de las comunas actuales. La identidad no debe depender solo del nombre si se amplía el catálogo a regiones distintas. Sin mantenedor nuevo.

### TarifaEnvio → costos_envio

`id: ID PK`, `comuna_id: ID FK UNIQUE`, `costo: entero >= 0`.

Una comuna tiene cero o una tarifa; para admitir checkout debe estar habilitada y tener exactamente una tarifa. Se preserva la separación actual de las dos tablas para facilitar la migración. Cambiar una tarifa no altera el costo guardado en pedidos previos.

### Caja → cajas

`id: ID PK`, `nombre: texto UNIQUE`, `cajero_id: ID REF?`.

Seed único «Web». La asignación puede faltar antes de configurar el sistema, pero ninguna compra nueva se admite sin un cajero activo validado por clients. No requiere sesión del cajero, apertura/cierre ni historial adicional de turnos.

### Pedido → ordenes

| Campos | Tipos y restricciones |
| --- | --- |
| id, cliente_id, operacion_checkout | ID PK; cliente_id REF a clients; checkout texto UNIQUE. |
| reserva_id, reserva_vence_en | ID REF a inventory UNIQUE cuando existe; fecha. Pueden ser null durante la coordinación técnica, nunca en un checkout completado. |
| estado, version | Enum pendiente/pagado/preparando/enviado/entregado/cancelado/expirado; entero >= 1. |
| subtotal, costo_envio, descuento, total, moneda | Enteros >= 0; moneda CLP. El descuento adicional queda en 0 en este alcance: ofertas ya incorporadas al precio de cada línea. |
| cliente_nombres, cliente_apellidos, cliente_email, cliente_telefono | Copias del contacto necesario al confirmar; email verificado en ese momento. No copiar RUT, nacimiento o sexo para el despacho. |
| calle, numero, departamento, comuna_id, comuna_nombre, ciudad, region | Dirección histórica: departamento nullable; comuna_id FK local, más textos que no cambian al editar la referencia. |
| caja_id, cajero_id | Caja FK local y cajero REF a clients; asignación aceptada en checkout, conservada para cobros ya iniciados. |
| pago_confirmado_id, pago_confirmado_en | ID REF a payments UNIQUE y fecha nullables; identifican el cobro aceptado para esta compra. |
| causa_cancelacion, motivo_cancelacion, cancelado_por, cancelado_en | Textos, ID REF y fecha nullables. Causa distingue cancelacion_normal de reembolso_excepcional. |

`subtotal = SUM(cantidad × precio_unitario)` de las líneas; `total = subtotal + costo_envio` para el alcance acordado. El servidor fija ambos. Los atributos resumidos se guardan para consulta y control, y se comprueban contra las líneas al crear; no se recalculan con el catálogo vigente.

El ID de pago aceptado y la versión evitan que un segundo cobro produzca otra venta. Un pago tardío o duplicado se conserva en payments y puede originar devolución sin promover el pedido a pagado. El orden de preparación utiliza pago_confirmado_en e ID.

### LineaPedido → lineas_orden

`id: ID PK`, `orden_id: ID FK`, `posicion: entero > 0`, `producto_id: ID REF?`, `combo_id: ID REF?`, `nombre: texto`, `cantidad: entero > 0`, `precio_unitario: entero >= 0`.

XOR producto_id/ combo_id y `UNIQUE(orden_id, posicion)`. Los IDs son referencias a inventory; quitar las FK actuales hacia sus tablas al separar las bases. Nombre, cantidad y precio son copias inmutables de LineaReserva. Un pedido completado en checkout tiene al menos una línea; pueden existir cabeceras técnicas aún no publicadas mientras se coordina el checkout.

### EventoPedido → eventos_pedido

`id: ID PK`, `orden_id: ID FK`, `tipo: texto controlado`, `estado_anterior: enum?`, `estado_resultante: enum`, `version_pedido: entero`, `actor_tipo: usuario/servicio`, `actor_id: texto`, `motivo: texto?`, `referencia_origen: texto`, `ocurrido_en: fecha`.

Historial aditivo: incluye creación, cambios de estado y avisos financieros relevantes que no cambian el estado operativo. Un evento financiero puede mantener estado_anterior = estado_resultante. Referencia única por pedido/tipo/origen evita registrar dos veces el mismo resultado. El DTO público muestra solo estado/fecha permitidos; no todos los campos de auditoría.

### Venta → ventas

`id: ID PK`, `orden_id: ID FK UNIQUE`, `pago_id: ID REF UNIQUE`, `caja_id: ID FK`, `cajero_id: ID REF`, `cajero_identificador: texto`, `total: entero >= 0`, `registrada_en: fecha`.

Cada pedido tiene cero o una venta; solo existe tras aceptar pago y consumo válido. La caja/cajero corresponden a los datos históricos del pedido. Cambiar la asignación de Caja no reescribe Venta. Un reembolso no elimina la venta ni cambia su fecha: el movimiento de devolución pertenece a payments.

### Comprobante → comprobantes

`id: ID PK`, `venta_id: ID FK UNIQUE`, `numero: texto UNIQUE`, `contenido_snapshot: texto`, `emitido_en: fecha`, `estado_envio: pendiente/simulado/fallido`, `mensaje_id: texto UNIQUE`, `destinatario_email: texto`, `intentos_envio: entero >= 0`, `ultimo_intento_en: fecha?`, `ultimo_error: texto?`.

Una venta tiene cero o un comprobante mientras se emite; debe alcanzar uno con emisión exitosa. Se construye una representación histórica con los datos de la venta/pedido y se conserva. No guardar aquí la contraseña del correo ni un token del proveedor. El envío usa el email verificado capturado al comprar, no el que un formulario arbitrario indique.

No se crea una fila nueva al reintentar emisión/envío. Si la emisión aún no produjo documento, el fallo y la tarea pendiente viven en la operación técnica; un fallo de correo conserva el comprobante ya emitido. El modo actual de entrega es simulado y debe aparecer así en la interfaz/evidencia.

## 5. payments

### IntentoPago → pagos

`id: ID PK`, `pedido_id: ID REF`, `cliente_id: ID REF`, `caja_id: ID REF`, `cajero_id: ID REF`, `proveedor: texto`, `transaccion_proveedor: texto?`, `estado: pendiente/aprobado/rechazado`, `monto: entero >= 0`, `moneda: CLP`, `vence_en: fecha`, `verificado_en: fecha?`, `aprobado_en: fecha?`.

Monto, dueño, caja y plazo se obtienen de I10 y quedan registrados; no los fija el navegador. Referencia de transacción única por proveedor cuando existe. Reutilizar el intento pendiente vigente; un rechazo permite otro intento sin extender la reserva. La exclusión de intentos pendientes se comprueba atómicamente por pedido.

Puede haber más de un cobro aprobado observado por errores/avisos tardíos; **no** impedir guardarlo con `UNIQUE(pedido_id)` para aprobados. Orders acepta solo uno para venta y coordina devolución de los cobros sobrantes. No guardar tarjetas, CVV ni credenciales del proveedor. La URL temporal del simulador no se expone en reportes o logs.

`aprobado_en` es la fecha efectiva del movimiento comprobada con el proveedor; `verificado_en` es cuándo payments lo verificó. El reporte usa la primera. Un aviso tardío no cambia artificialmente la fecha del cobro ni autoriza consumo de una reserva vencida.

### EventoProveedor → eventos_proveedor

`id: ID PK`, `proveedor: texto`, `evento_proveedor: texto`, `tipo: pago`, `pago_id: ID FK?`, `transaccion_proveedor: texto`, `resumen_validado: texto JSON mínimo`, `recibido_en: fecha`, `verificado_en: fecha?`, `procesado_en: fecha?`.

`UNIQUE(proveedor, evento_proveedor)`. Solo se persisten como eventos aceptados notificaciones con autenticación válida; después se contrasta su contenido con la consulta de estado al proveedor antes de aplicar efectos. La transacción/referencia permite enlazar un aviso recibido antes de completar la llamada de inicio. Los duplicados no generan otra fila ni efectos; un aviso que falló se procesa al reenviarlo explícitamente. No hay un worker de eventos ni avisos de reembolso.

### SolicitudReembolso → solicitudes_reembolso

`id: ID PK`, `pedido_id: ID REF`, `pago_id: ID FK`, `cliente_id: ID REF`, `motivo: texto 1–1000`, `estado: pendiente/aprobada/rechazada`, `version: entero >= 1`, `decision_id: texto UNIQUE?`, `administrador_id: ID REF?`, `motivo_decision: texto?`, `decidida_en: fecha?`.

Una solicitud pertenece a un pedido y al cobro aceptado que pretende devolver. Permite antecedentes solo textuales. Decisión y actor quedan registrados de forma inmutable al resolver. Un pedido puede tener varias solicitudes históricas rechazadas, pero como máximo una pendiente o aprobada. El chequeo del proceso activo también contempla reembolsos técnicos; se realiza en una transacción local de payments.

### Reembolso → reembolsos

`id: ID PK`, `pago_id: ID FK UNIQUE`, `solicitud_id: ID FK UNIQUE?`, `causa: cancelacion_pagada/pago_tardio/cobro_duplicado/excepcional`, `referencia_autorizacion: texto`, `estado: pendiente/completado/fallido`, `monto_solicitado: entero >= 0`, `monto_devuelto: entero >= 0`, `moneda: CLP`, `completado_en: fecha?`.

Un proceso por cobro, porque solo se devuelven saldos íntegros. `solicitud_id` es obligatorio únicamente para causa excepcional y debe estar aprobada; las causas técnicas no inventan una solicitud del Cliente. El pedido se obtiene del pago; no duplicarlo sin necesidad en esta tabla. Una operación devuelve siempre la causa/autorización guardadas, nunca un nuevo importe arbitrario.

`0 <= monto_devuelto <= monto_solicitado <= monto cobrado verificado`. Pendiente/fallido no cuentan como dinero devuelto; completado cuenta una vez por su fecha efectiva verificada. Distintos cobros duplicados del mismo pedido pueden tener sus propios reembolsos técnicos. No se vuelve a modificar stock al cambiar el estado financiero.

### IntentoReembolso → intentos_reembolso

`id: ID PK`, `reembolso_id: ID FK`, `numero_intento: entero > 0`, `referencia_proveedor: texto?`, `clave_proveedor: texto UNIQUE`, `estado: pendiente/completado/fallido`, `iniciado_por: ID REF?`, `error_controlado: texto?`, `verificado_en: fecha?`, `completado_en: fecha?`.

`UNIQUE(reembolso_id, numero_intento)` y referencia única por proveedor cuando existe. El primer intento puede ser técnico; un reintento nuevo requiere Administrador y fallo definitivo del anterior. Si el resultado es incierto, se consulta/reutiliza el mismo intento y su clave. El proceso conserva su ID y aprobación; los intentos conservan la historia de fallos sin duplicar dinero.

## 6. Relaciones y cardinalidades

Cada fila indica cuántos destinos puede tener **un origen** y a cuántos orígenes pertenece **un destino**. FK son asociaciones locales; REF son relaciones del negocio entre servicios, no claves foráneas distribuidas.

| Origen → destino | Destinos por origen | Orígenes por destino | Tipo y justificación |
| --- | --- | --- | --- |
| Cliente → Usuario | 0..1 | 0..1 | FK UNIQUE: registro sin acceso aún; funcionario sin Cliente. Usuario con rol cliente exige exactamente un Cliente. |
| Usuario → Sesion | 0..* | 1 | FK: varios accesos, cada sesión de una cuenta. |
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

## 7. Persistencia técnica y recuperación

Además de las 23 tablas principales, cada servicio que ejecute acciones repetibles necesita su registro local `operaciones`. Es soporte técnico y no añade un estado comercial nuevo al pedido.

Campos implementados: `id`, `actor`, `tipo`, `clave`, `solicitud_hash`, `datos` JSON, `resultado` JSON, `status`, `creado_en` y `actualizado_en`. La combinación actor/tipo/clave es única.

- La misma clave y contenido devuelve el resultado guardado; otro contenido produce 409.
- Las referencias de pedido/pago se guardan para que el cliente pueda repetir explícitamente una operación interrumpida. No hay un coordinador que retome operaciones en segundo plano.
- El aviso de pago se verifica y procesa durante la solicitud; `eventos_proveedor` evita repetir sus efectos. El simulador permite reenviar el mismo resultado si falló una dependencia.
- Las devoluciones usan su referencia idempotente y reintento manual del Administrador. La unicidad de venta, comprobante y reembolso se conserva.
- Solo el vencimiento de reservas se comprueba periódicamente. No se diseñan colas, purga automática ni infraestructura de producción para esta entrega.

El diagrama de dominio conserva la propuesta del 24 de octubre como referencia; su relación adicional de avisos de reembolso no se utiliza en el alcance simplificado. Los SQL de `services/<servicio>/schema.sql` describen las tablas realmente implementadas. Bases creadas antes de simplificar pueden conservar columnas técnicas sin uso; no se eliminan datos para actualizar la demostración.

## 8. Índices y restricciones prioritarios

- clients: RUT/email normalizados, identificador y usuario por Cliente.
- auth: sesiones por usuario y vencimiento.
- inventory: productos por categoría/activo; componentes por combo y producto; reservas por referencia única y por estado/vencimiento; detalles por producto/reserva.
- orders: pedidos por cliente/fecha/ID; estado/pago_confirmado_en/ID para Despacho; historial por pedido/fecha/ID; únicos de reserva, venta por pedido/pago y comprobante por venta/número.
- payments: pagos por pedido/creación/ID y transacción del proveedor; eventos por ID externo; solicitudes por pedido/estado; reembolso único por pago; intentos por reembolso/número.
- Excluir una segunda solicitud pendiente/aprobada mediante índice único parcial por pedido. Reutilizar un intento pendiente por pedido mediante control transaccional/índice parcial; avisos tardíos que contradigan una salida terminal se concilian contra el proveedor, no se descartan para preservar el índice.
- La validación de sumas, mínimos de líneas, roles activos y reglas entre servicios pertenece a los servicios además de las restricciones SQL locales.

## 9. Valores calculados y datos que no se duplican

| Concepto | Tratamiento |
| --- | --- |
| Carrito | Frontend; sin tabla ni reserva, como ya se acordó. |
| Disponible/Agotado | Derivado de stock libre, actividad y componentes; solo ese indicador sale al catálogo público. |
| Stock disponible y reservado | Calculados en inventory; sin contadores independientes persistidos en esta propuesta. |
| Estado financiero del pedido | Proyección de payments; no es un octavo estado operativo. |
| Reporte de ventas | Consulta a ventas y movimientos verificados; sin tabla de reportes o analítica nueva por defecto. |
| Precio, nombre y contacto históricos | Copias justificadas en la compra; no se sincronizan con ediciones posteriores. |
| Precio actual del catálogo | Consulta independiente a inventory; nunca reescribe la línea histórica. |
| Permisos y secretos | Roles/control de autorización en código y configuración; secretos de integración en Vault. No tabla pública de secretos. |

## 10. Correspondencia con lo existente y los contratos

| Área | Mantener/adaptar | Incorporar | Contratos relacionados |
| --- | --- | --- | --- |
| clients | clientes, usuarios, sesiones; quitar FK a comuna externa y agregar etiqueta del perfil; normalización/unicidad del email. | Revocación/fechas y controles de identidad del modelo. | S01–S05, S07–S12, I01–I03, G04. |
| inventory | categorias, productos, combos, lineas_combo; agregar activo a producto. | reservas, lineas_reserva, detalles_reserva y atomicidad. | S13–S19, I04–I09, G03; enriquecimiento G02. |
| orders | comunas, costos_envio, cajas, ordenes, lineas_orden, ventas; quitar FK hacia otros servicios. | eventos_pedido, comprobantes; snapshots, referencias y versión. | S06, S20–S33, I10–I13, I18, G01/G02/G05/G06. |
| payments | No hay esquema propio equivalente actual. | pagos, eventos_proveedor, solicitudes_reembolso, reembolsos, intentos_reembolso. | S34–S40, S42, I14–I17; G01/G02/G05/G06 según permisos. |

Al migrar, normalizar pagada/enviada/entregada/cancelada a pagado/enviado/entregado/cancelado y admitir expirado. Retirar como autoridades los campos financieros antiguos de ordenes/ventas; el comprobante y su envío pasan a su entidad, los cobros/devoluciones a payments. Antes de cargar un índice nuevo, detectar datos previos incompatibles; no borrar registros para forzarlo.

## 11. Simuladores y límites pendientes

El proveedor simulado conserva **sus propios datos**, separados del estado oficial de payments: transacción, monto/moneda, resultado, fecha efectiva, hash del token de checkout y referencias de reembolso/eventos. Las operaciones M01–M06 se implementan sobre ese almacenamiento persistente; payments solo cambia por contrato autenticado y verificación. No editar directamente `pagos.estado` desde la pantalla del simulador.

El correo simulado conserva el resultado y la referencia del mensaje en clients/operaciones para verificación y en comprobantes/operaciones para ventas. No se agrega una plataforma de mensajería ni integración de email real en esta etapa.

Este modelo define los cuatro servicios propios. No sustituye el diseño físico/migraciones, el inventario de datos/retención, la decisión de gRPC/analítica, el UML de servicios y gateway, ni las pruebas de concurrencia/fallos. La aceptación de los adaptadores simulados frente al módulo 10 sigue siendo una limitación por resolver con la pauta del docente.

## 12. Comprobación del diseño con escenarios

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
