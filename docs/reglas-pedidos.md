# Reglas de negocio

Este documento define las reglas de negocio para la implementación del sistema. En ellas se consideran los siguientes aspectos:
 
- Módulos del backend
- Catálogo de endpoints
- Carrito
- Estados de pedido
- Transiciones y permisos
- Reservas y stock
- Anulaciones y reembolsos
- Despacho, caja, comprobantes y reportes
- Sesiones y límites de acceso
- Escenarios de comprobación

Cada sección especifica qué contempla el sistema, qué puede ocurrir, bajo qué condiciones y con qué consecuencias.

**Actualización del 28 de octubre de 2026:** backend académico en `services/`, con 61 contratos propios, seis consultas GraphQL y pagos/correo simulados. Se conservan las reglas funcionales acordadas el 24 de octubre. Ver [contratos REST](contratos-rest.md), [GraphQL](contratos-graphql.md) y [estado comprobado](estado-backend-e2.md).

**Alcance educativo:** los pagos se verifican y aplican durante la misma solicitud. Ante una dependencia caída, se repite la operación con la misma clave o se reenvía el aviso del simulador. No hay recuperación automática de pagos/cancelaciones en segundo plano, caché de consultas ni rotación automática de secretos. La única tarea periódica vence las reservas. Vault se lee al arrancar; cambiar credenciales requiere reiniciar los servicios. Los límites del gateway usan contadores en memoria por minuto fijo. No se agrega infraestructura de producción como objetivo del proyecto.

El [modelo de datos propuesto](modelo-datos.md) traduce estas reglas a entidades, atributos y cardinalidades; su [diagrama de dominio editable](modelo-dominio.mmd) todavía debe complementarse con el UML de servicios y gateway.

**Adaptaciones de Fit Express:** SQLite/FastAPI, cuatro microservicios privados y GraphQL obligatorio. El despacho usa comunas habilitadas con tarifa fija, en lugar de la entrega gratuita en un radio de 3 km del caso 19 de referencia. Pagos y correo serán simulados; email real y su proveedor se posponen. La rúbrica exige coherencia con el caso e identificar las limitaciones de adaptadores de prueba: estas adaptaciones se registran expresamente, sin afirmar una integración externa real.

---

## Módulos del backend

El diseño contempla cuatro microservicios privados. Cada uno administra sus propios datos y se comunica con los demás mediante contratos internos autenticados. La implementación nueva está en `services/`; su separación por contratos, arranque con Docker/Vault real y compra completa están comprobados.

### clients

Administra perfiles, cuentas, roles, hashes y verificación de correo. Expone las cuentas solo a Auth mediante APIs privadas; no administra sesiones ni emite tokens. El perfil se consulta mediante GraphQL `perfil`, que utiliza `GET /perfil` privado.

### auth

Servicio separado, siguiendo el ejemplo del profesor. Implementa `POST /login`, `POST /introspect` y `POST /logout`. Login recibe `username/password`, consulta la cuenta privada de clients, valida el hash y crea una sesión en su propio SQLite. Devuelve `access_token`, `token_type: bearer` y `expires_in: 28800`.

El gateway recibe `Authorization: Bearer <access_token>`, consulta `/introspect` y transmite el usuario y rol comprobados en `X-Authenticated-*`, junto con `X-Gateway-Secret`. Los servicios verifican su llamador y sus permisos de negocio; no vuelven a consultar la sesión. El token personal no sale del gateway hacia los servicios de negocio. Logout revoca la sesión; cambios de cuenta invalidan la versión asociada al token.

### inventory

Administra categorías, productos, combos, precios, disponibilidad, stock y reservas. Reserva las unidades durante 15 minutos al confirmar el checkout, confirma su consumo al pagar y las libera al vencer o cancelar antes del pago. También restituye las unidades cuando corresponde cancelar un pedido pagado antes de su preparación.

### orders

Administra pedidos, líneas, dirección de entrega, comunas habilitadas, tarifas de despacho, totales, estados e historial. Crea el pedido al confirmar el checkout y calcula el total con los precios de inventory. Coordina cancelaciones, preparación y despacho, así como las ventas, cajas y comprobantes asociados. Solicita las operaciones de stock y dinero a inventory y payments, manteniendo la autoridad sobre el estado del pedido.

### payments

Administra intentos de pago, resultados verificados y reembolsos. Obtiene el monto oficial desde orders, inicia el pago con el proveedor y verifica su resultado sin duplicar efectos ante notificaciones repetidas. Informa el resultado a orders y ejecuta las devoluciones correspondientes a cancelaciones pagadas, pagos tardíos o solicitudes excepcionales aprobadas por un administrador.

### Acceso a los módulos

El API Gateway recibe las solicitudes del frontend y las dirige a los servicios autorizados. El GraphQL Gateway es privado y entrega las lecturas de catálogo, perfil, historial, detalle, gestión de pedidos y reporte de ventas. Combina módulos cuando la pantalla lo necesita, como orders y payments en Mis pedidos. Las acciones se mantienen en REST y cada módulo conserva sus validaciones de negocio y permisos.

HashiCorp Vault administra los secretos de integración que utilizan los componentes para comunicarse. El gateway ya consulta esos secretos en Vault. Auth identifica a los usuarios mediante sus credenciales y sesiones; Vault mantiene la custodia de los secretos de integración como una responsabilidad separada.

---

## Catálogo de endpoints

Este catálogo define las rutas objetivo para los cuatro módulos, Auth y GraphQL. Es un diseño basado en las reglas del caso y las pantallas; no significa que las rutas nuevas estén implementadas. Los IDs S, I y G permiten vincular contratos de servicio, integraciones y operaciones GraphQL con pantallas, requisitos, permisos y pruebas. Se conservan los IDs S de las lecturas que pasan a ser privadas para mantener su trazabilidad.

### Convenciones

- Las tablas de los módulos muestran la ruta de servicio sin `/api`. Para los contratos REST públicos, el navegador usa, por ejemplo, `/api/ordenes`; las seis consultas GraphQL usan `POST /api/graphql`. El API Gateway dirige cada solicitud al componente privado correspondiente.
- Las rutas `/interno/...` y las ocho lecturas marcadas como privadas en la distribución siguiente son únicamente entre componentes autorizados. La lista pública del API Gateway excluye ambas clases de contratos; el prefijo no determina por sí solo la exposición.
- La columna de estado conserva el diagnóstico del **24 de octubre**: **Existente** era una ruta del backend histórico, **Renombrar** un cambio propuesto y **Nuevo** una ruta entonces pendiente. Al 28 de octubre, los 61 contratos están presentes en `services/`; el estado de ejecución y sus límites se registra en `estado-backend-e2.md`.
- La query `perfil` reemplaza el uso de `/yo` desde el frontend y se resuelve con `GET /perfil` privado de clients. El backend, `frontend/src/api.js`, checkout, cuenta, panel y pruebas todavía usan `/yo`; la migración deberá hacerse conjuntamente, sin retirarlo antes de actualizar sus consumidores.
- Paginación: `pagina` desde 1; catálogo con 12 elementos por defecto y los demás listados con 20; máximo 50. Filtros antes de paginar y orden estable. Se comprueban sesión, rol, propiedad/caja y estado con campos mínimos por actor.
- No se agregan endpoints de carrito: la selección se mantiene en el frontend y no reserva stock. Clientes y usuarios se desactivan mediante PATCH; no se elimina su historial ni se ofrece DELETE de pedidos.

### Distribución entre REST y GraphQL

GraphQL reúne las lecturas de las seis consultas acordadas. Los servicios conservan sus APIs REST privadas y la autoridad sobre sus datos. Estas ocho lecturas dejan de ser rutas REST públicas cuando sus pantallas hayan migrado:

| Contrato de servicio privado | Lectura desde el frontend | Responsable |
| --- | --- | --- |
| S03 `GET /perfil` | G04 `perfil` | clients |
| S13 `GET /categorias` | G03 `catalogo` | inventory |
| S14 `GET /productos` | G03 `catalogo` | inventory |
| S15 `GET /productos/{id}` | G03 `catalogo`, filtrando por producto; G02 puede enriquecer las líneas mediante I04 | inventory |
| S16 `GET /combos` | G03 `catalogo` | inventory |
| S21 `GET /ordenes` | G01 `misPedidos` o G05 `pedidos`, según actor | orders |
| S22 `GET /ordenes/{id}` | G02 `pedido` | orders |
| S30 `GET /reportes/ventas` | G06 `reporteVentas` | orders |

Los demás contratos S conservan su acceso REST autorizado: autenticación, registro/verificación, comunas, mantenedores y sus listados, cajas, acciones sobre pedidos/pagos/reembolsos, consultas específicas de pagos y solicitudes de reembolso, webhooks y documentos. El alcance inicial no incluye mutations ni subscriptions. El objetivo reúne 34 rutas públicas por el API Gateway y 26 contratos privados: las ocho lecturas anteriores más I01–I18. Son 61 contratos HTTP propios; los seis del simulador de pagos y la salud técnica se documentan aparte. Las seis queries comparten S41; no añaden seis URLs.

La migración se hace por pantalla, reutilizando la lógica y los permisos del servicio. Mientras se actualizan los consumidores pueden coexistir ambas entradas bajo los mismos controles; después se retira la ruta REST migrada de la lista pública del gateway. El backend histórico conserva sus rutas originales. El gateway nuevo publica las acciones y GraphQL; el frontend no se migró por instrucción del usuario.

### clients y Auth

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| S01 | `POST /login` (auth) | Validar credenciales y crear una sesión; cliente con correo verificado. | Sin sesión previa; credenciales válidas. | Existente; adaptar al servicio y controles definidos. |
| S02 | `POST /logout` (auth) | Revocar la sesión del solicitante. | Usuario con sesión válida. | Existente; adaptar al servicio y controles definidos. |
| S03 | `GET /perfil` | Consultar identidad, rol y perfil del usuario actual; contrato privado para G04. | GraphQL con identidad de servicio y sesión válida del usuario; solo sus propios datos. | Renombrar desde `GET /yo` y migrar frontend a `perfil`; pendiente. |
| S04 | `POST /registro` | Registrar cliente e iniciar verificación de correo. | Visitante; validación y límite de solicitudes. | Existente; adaptar al servicio y controles definidos. |
| S05 | `POST /clientes/verificar-correo` | Validar código vigente y habilitar la cuenta; conservar el flujo actual de definición de contraseña. | Titular con código de verificación válido. | Existente; adaptar al servicio y controles definidos. |
| S07 | `GET /admin/clientes` | Listar clientes con paginación y campos necesarios para administración. | Administrador. | Existente; adaptar al servicio y controles definidos. |
| S08 | `POST /admin/clientes` | Registrar cliente desde el local; también exige verificación de correo. | Administrador. | Existente; adaptar al servicio y controles definidos. |
| S09 | `PATCH /admin/clientes/{id}` | Actualizar o desactivar cliente; aplicar política de sesiones y nueva verificación si cambia el correo. | Administrador. | Existente; adaptar al servicio y controles definidos. |
| S10 | `GET /admin/usuarios` | Listar funcionarios con filtros y paginación; no devuelve hashes ni sesiones. | Administrador. | Existente; adaptar al servicio y controles definidos. |
| S11 | `POST /admin/usuarios` | Crear funcionario con un rol permitido. | Administrador. | Existente; adaptar al servicio y controles definidos. |
| S12 | `PATCH /admin/usuarios/{id}` | Actualizar rol, credenciales o estado activo del funcionario; controlar sesiones afectadas. | Administrador. | Existente; adaptar al servicio y controles definidos. |

### inventory

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| S13 | `GET /categorias` | Listar categorías del catálogo; contrato privado para G03. | GraphQL autorizado técnicamente; contexto anónimo permitido para campos públicos. | Existente; adaptar y migrar lectura pública a GraphQL. |
| S14 | `GET /productos` | Consultar catálogo y disponibilidad con filtros/paginación; contrato privado para G03. | GraphQL autorizado técnicamente; anónimo para catálogo público, ofertas según identidad verificada. | Existente; adaptar y migrar lectura pública a GraphQL. |
| S15 | `GET /productos/{id}` | Consultar un producto con campos permitidos; contrato privado del catálogo. | GraphQL autorizado técnicamente; anónimo para datos públicos, ofertas según identidad verificada. | Existente; adaptar y migrar lectura pública a GraphQL. |
| S16 | `GET /combos` | Consultar combos, componentes y disponibilidad calculada; contrato privado para G03. | GraphQL autorizado técnicamente; anónimo para catálogo público, ofertas según identidad verificada. | Existente; adaptar y migrar lectura pública a GraphQL. |
| S17 | `POST /productos` | Crear producto con validación de categoría, precio y stock. | Administrador o Dueño. | Existente; adaptar al servicio y controles definidos. |
| S18 | `PUT /productos/{id}` | Actualizar producto completo; proteger unidades reservadas y datos de compras anteriores. | Administrador o Dueño. | Existente; adaptar al servicio y controles definidos. |
| S19 | `DELETE /productos/{id}` | Desactivar sin borrar: ocultar del catálogo y dejar no disponibles sus combos, conservando reservas comprometidas e historial. | Administrador o Dueño. | Existente; adaptar al servicio y controles definidos. |

Los combos y categorías quedan preconfigurados en los datos iniciales, sin nuevos mantenedores. Los precios, ofertas, disponibilidad y stock reservado se calculan en inventory. Una actualización no puede dejar stock por debajo de lo comprometido en reservas. Se acuerda mostrar únicamente Disponible/Agotado en el catálogo público, sin cantidades exactas; el stock administrativo queda restringido a Administrador y Dueño. El catálogo público no devuelve secretos ni datos personales.

### orders

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| S06 | `GET /comunas` | Listar comunas habilitadas y tarifa oficial de despacho; referencia también usada en registro/perfil. | Anónimo; datos públicos. | Existente; extraer a orders por su autoridad sobre cobertura/tarifas. |
| S20 | `POST /ordenes` | Confirmar checkout: validar cobertura, fijar total y crear pedido con reserva completa de 15 minutos. | Cliente con sesión y correo verificado; comprador obtenido de la sesión. | Existente; adaptar al servicio y controles definidos. |
| S21 | `GET /ordenes` | Listar pedidos paginados con filtros por estado/fechas; contrato privado para G01/G05. Cola por pago confirmado e ID ascendentes; los demás listados por creación e ID descendentes. | GraphQL con identidad técnica y usuario verificado. Cliente: propios; Administrador: gestión; Cajero: caja asignada; Despacho: cola y campos operativos. | Nuevo; pendiente. |
| S22 | `GET /ordenes/{id}` | Consultar pedido, líneas e historial; contrato privado para G02 con campos mínimos según rol. | GraphQL con identidad técnica y usuario verificado. Cliente propietario; Administrador; Cajero de su caja; Despacho según finalidad operativa. | Existente; adaptar y migrar lectura pública a GraphQL. |
| S23 | `POST /ordenes/{id}/cancelaciones` | Cancelar pedido pendiente o pagado antes de preparación, con motivo; coordinar stock y devolución cuando corresponda. | Cliente propietario o Administrador. | Nuevo; pendiente. |
| S24 | `POST /ordenes/{id}/preparacion` | Registrar inicio de preparación únicamente desde pagado y sin cancelación aceptada. | Despacho. | Nuevo; pendiente. |
| S25 | `POST /ordenes/{id}/envios` | Registrar salida a reparto únicamente desde preparando. | Despacho. | Nuevo; pendiente. |
| S26 | `POST /ordenes/{id}/entregas` | Registrar entrega únicamente desde enviado. | Despacho. | Nuevo; pendiente. |
| S27 | `GET /ordenes/{id}/orden-despacho` | Obtener documento imprimible para cocina y despacho de un pedido pagado; no equivale a iniciar preparación. | Despacho; campos mínimos necesarios. | Nuevo; pendiente. |
| S28 | `GET /cajas` | Consultar caja Web y asignación vigente; no crear CRUD adicional para cajas sin un requisito. | Administrador; Cajero: solo su caja. | Nuevo; pendiente. |
| S29 | `PATCH /cajas/{id}` | Asignar cajero activo y con rol cajero; validar identidad del funcionario mediante clients. | Administrador. | Nuevo; pendiente. |
| S30 | `GET /reportes/ventas` | Consultar ventas y total por período desde/hasta; contrato privado para G06. Separar ventas, anulaciones y devoluciones para evitar dobles conteos. | GraphQL con identidad técnica y usuario Administrador o Dueño; datos personales mínimos. | Nuevo; pendiente. |
| S31 | `POST /ventas/{id}/comprobantes` | Emitir la boleta digital única de una venta confirmada y solicitar su envío; reintento no crea otra boleta. | Cajero de la caja de la venta. | Nuevo; pendiente. |
| S32 | `GET /ventas/{id}/comprobante` | Consultar o descargar el comprobante ya emitido. | Cliente propietario; Cajero de su caja; Administrador para gestión. | Nuevo; pendiente. |
| S33 | `POST /ventas/{id}/comprobante/envios` | Reintentar envío de la boleta al correo verificado del cliente; conserva resultado y error del envío. | Cajero de la caja de la venta. | Nuevo; pendiente. |

- El checkout recibe ítems y dirección; la identidad proviene de la sesión y el servidor fija total, envío y estado. Orders exige una comuna habilitada, aplica su tarifa configurada y conserva el costo aceptado. No se calculan distancias ni redondeos por kilómetro.
- La cola de despacho se presenta mediante G05 `pedidos`, que consulta `GET /ordenes` privado con los estados y campos autorizados para Despacho y orden de llegada a preparación. Obtenerla no modifica el estado de los pedidos.
- Existe una única caja Web con cajero habilitado asignado por Administrador. Opera automáticamente sin que el cajero esté conectado ni apertura/cierre manual. Se valida al admitir compras/cobros; cada venta conserva su caja/cajero históricos.
- Confirmar un pago registra una venta única, emite automáticamente un comprobante único y solicita su envío simulado; el proceso interno autorizado usa la lógica de orders en nombre de la caja y cajero registrados. Las rutas de comprobantes permiten al cajero emitir o reintentar lo pendiente sin duplicar documentos.
- `GET /ordenes/{id}/orden-despacho` entrega una vista imprimible; obtenerla no demuestra que se imprimió ni cambia el pedido a preparando.

### payments

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| S34 | `POST /pagos` | Crear un intento para orden_id; monto y moneda se obtienen de orders. Un reintento real crea otro intento sin duplicar la venta. | Cliente propietario con reserva vigente o Cajero de la caja asignada. | Nuevo; pendiente. |
| S35 | `GET /pagos/{id}` | Consultar resultado verificado e información mínima del intento. | Cliente propietario; Cajero de su caja; Administrador para evaluar devoluciones. | Nuevo; pendiente. |
| S36 | `POST /webhooks/pagos/{proveedor}` | Recibir y verificar avisos de pagos/devoluciones con el contrato del proveedor; deduplicar eventos y conciliar resultados. | Proveedor autenticado por su mecanismo de integración; no depende de una sesión de usuario. | Nuevo; pendiente. |
| S37 | `POST /solicitudes-reembolso` | Registrar solicitud excepcional por pedido en preparación o posterior, con motivo y antecedentes únicamente textuales; una solicitud activa por pedido. | Cliente propietario; pago verificado. | Nuevo; pendiente. |
| S38 | `GET /solicitudes-reembolso` | Listar solicitudes paginadas, incluyendo pendientes de decisión. | Cliente: propias; Administrador: gestión. | Nuevo; pendiente. |
| S39 | `GET /solicitudes-reembolso/{id}` | Consultar motivo/antecedentes textuales, decisión y estado de devolución. | Cliente propietario o Administrador. | Nuevo; pendiente. |
| S40 | `POST /solicitudes-reembolso/{id}/decisiones` | Aprobar o rechazar con razón. Al aprobar, coordinar I18: cancelar si sigue preparando, sin recuperar stock; enviado/entregado conserva su recorrido. Devolver todo el saldo y registrar resultado financiero separado. | Solo Administrador. | Nuevo; pendiente. |
| S42 | `POST /reembolsos/{id}/reintentos` | Reintentar/reconciliar una devolución fallida o incierta, sin nueva aprobación ni repetir stock/venta. | Administrador; causa/autorización original válidas. | Nuevo; pendiente. |

- El cliente y el cajero pueden iniciar operaciones permitidas, pero el proveedor y payments son quienes acreditan su resultado. Las rutas de negocio no permiten asignar `pagado`, `aprobado` o un monto arbitrario. La pantalla separada del simulador produce resultados de prueba que payments verifica.
- Los webhooks llegan por el API Gateway al servicio privado payments y aplican autenticación del proveedor, sin exigir una sesión humana. El proveedor elegido es un simulador con pantalla de aprobado/rechazado/pendiente. Se verifica firma y se consulta su estado por API privada; ni el cuerpo ni el retorno del navegador acreditan el pago por sí solos.
- `solicitudes-reembolso` representa la excepción posterior al inicio de preparación, con motivo/antecedentes textuales y decisión administrativa. Las devoluciones por cancelación pagada o pago tardío se ejecutan por integración interna, sin exigir una solicitud excepcional que no corresponde a esos casos.
- Los reembolsos comerciales son completos: todo el saldo pagado pendiente de devolución, sin importes parciales ingresados por usuarios. Un cobro duplicado se concilia/devuelve por su referencia, sin otra venta.
- Una solicitud/proceso activo por pedido. Tras rechazo se admiten nuevos antecedentes; si ya fue aprobada pero falla la devolución, Administrador reintenta el mismo proceso sin otra aprobación. Un saldo ya devuelto no se devuelve otra vez.
- Las referencias e idempotencia se conservan. Ante un resultado incierto, se repite la misma referencia idempotente del proveedor y se verifica su resultado; no se crea un intento nuevo hasta conocer el resultado anterior.
- La solicitud y su decisión necesitan vistas de cliente/administrador; son flujos definidos en estas reglas y todavía no están conectados en el frontend.

### GraphQL Gateway

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| S41 | `POST /graphql` | Ejecutar las seis queries acordadas mediante APIs privadas de inventory, clients, orders y payments; agregar servicios cuando los campos lo requieren. | Anónimo para catálogo público; sesión y permisos por operación/recurso/campo para el resto. | Nuevo; pendiente. |

El API Gateway expone un único `POST /api/graphql` y lo dirige al `POST /graphql` del agregador privado. Se acuerdan seis consultas; G01/G02 conservan sus IDs originales:

| ID | Query | Propósito y pantalla | Acceso | Subsistemas y contratos |
| --- | --- | --- | --- | --- |
| G01 | `misPedidos(filtros, pagina, limite)` | Historial propio con estado operativo y resumen verificado del pago; Mi cuenta → Mis pedidos. | Cliente; la identidad decide el propietario, sin un cliente_id arbitrario. | orders S21 + payments I16 por lote. |
| G02 | `pedido(id)` | Detalle, líneas históricas, seguimiento, pago y devolución cuando corresponda. Puede incluir información actual de los productos, separada de la compra histórica. | Cliente propietario; Administrador; Cajero de su caja; Despacho solo campos operativos y datos necesarios para cumplir el pedido. | orders S22 + payments I16 si se solicitan campos permitidos + inventory I04 para datos actuales. |
| G03 | `catalogo(filtros, pagina, limite)` | Categorías, productos, combos y disponibilidad para catálogo y selección del carrito; admite filtro por ID de producto. | Anónimo para campos públicos; ofertas según identidad verificada y política de inventory. | inventory S13–S16; cada listado solicitado tiene paginación y límite propios. |
| G04 | `perfil` | Identidad, rol y datos propios para Mi cuenta, navegación y datos del comprador en checkout. | Usuario autenticado; identidad obtenida de la sesión, sin ID de otro usuario. | clients S03. |
| G05 | `pedidos(filtros, pagina, limite)` | Gestión y seguimiento de pedidos; incluye la cola de preparación/despacho según rol. | Administrador: gestión; Cajero: caja asignada; Despacho: estados y campos operativos. No amplía el alcance mediante filtros. | orders S21; payments I16 solo para campos financieros permitidos al Administrador/Cajero. |
| G06 | `reporteVentas(desde, hasta, pagina, limite)` | Reporte del período con ventas de orders y resumen de cobros/devoluciones de payments. | Administrador o Dueño; resumen financiero y datos personales mínimos. | orders S30 + payments I17. Los módulos calculan sus indicadores. |

- La responsabilidad de GraphQL es resolver los campos solicitados y componer las respuestas. Cada servicio conserva precios, disponibilidad, cobertura, estados, pagos, reglas de autorización y cálculos bajo su autoridad. GraphQL utiliza APIs privadas; no consulta bases de otros módulos.
- Las consultas mantienen los precios y descripciones históricos guardados en orders; distinguen los datos actuales de inventory y toleran productos retirados. La indisponibilidad del catálogo no borra líneas de la compra.
- La sesión se comprueba mediante Auth cuando está presente o la operación la requiere. El catálogo público admite contexto anónimo, pero las llamadas entre componentes siempre llevan identidad técnica válida. Los servicios vuelven a comprobar el contexto y el acceso a sus recursos.
- El schema restringe campos financieros, datos personales y detalles de devolución según actor. Despacho recibe el estado operativo y los datos necesarios para preparar/entregar; no los intentos de pago ni el expediente de reembolso. Dueño accede al resumen del reporte sin heredar los permisos administrativos sobre pedidos o clientes.
- El gateway aplica paginación, límites de profundidad/costo/tamaño, plazos y batching. I04 e I16 tienen lotes acotados; se agrupan los datos de una página o pedido para los actores autorizados, sin una llamada por cada línea o pedido. No se inspecciona la selección de campos para optimizar llamadas. Las consultas públicas también están sujetas a límites.
- Un fallo de payments no convierte un pago en rechazado ni un reembolso en cero. Los campos afectados devuelven un error controlado; el resto de datos autorizados puede mantenerse. En reportes se indica que el resultado está incompleto.
- G06 es básico: listado paginado, cantidad de ventas, total cobrado, total devuelto y neto cobrado. Cada movimiento financiero usa su propia fecha y el neto puede ser negativo. Se interpretan días en America/Santiago, con límite superior exclusivo al comenzar el día siguiente. No incluye rankings/desgloses. Orders cuenta/lista ventas; payments calcula sus totales.
- Las escrituras iniciales se realizan mediante los endpoints REST definidos; no se incluyen mutations ni subscriptions. `POST /graphql` no autoriza cualquier operación o campo.

**Orden de implementación acordado:** empezar por G03 `catalogo` para conectar la pantalla existente y G02 `pedido` para demostrar agregación entre servicios; luego integrar G04 `perfil`, G01 `misPedidos`, G05 `pedidos` y G06 `reporteVentas`. Los argumentos, tipos, permisos, schema de contrato y ejemplos de las seis queries están en [contratos-graphql.md](contratos-graphql.md). Resolvers, adaptaciones y ejecución real siguen pendientes; estas definiciones no acreditan funcionalidad implementada.

### Integraciones internas

Todas las rutas siguientes son propuestas nuevas. Cada llamada exige identidad de servicio válida y alcance para la operación; cuando actúa por un usuario, también conserva el contexto verificado de ese usuario. Los secretos se obtienen de Vault y no se devuelven al frontend.

#### Auth y clients

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| I01 | `POST /introspect` (auth) | Validar token y devolver active, user_id, username, roles y referencias de cliente. | Solo API Gateway con secretos de integración. | Implementado. |
| I19 | `POST /interno/auth/credenciales` (clients) | Obtener cuenta y hash para validar el login. | Solo Auth; nunca público ni GraphQL. | Implementado. |
| I02 | `GET /interno/clientes/{id}` | Obtener datos mínimos del comprador para la orden/boleta; no devolver todo el registro de cliente. | orders, con finalidad y contexto de usuario autorizados. | Nuevo; pendiente. |
| I03 | `GET /interno/usuarios/{id}` | Comprobar existencia, rol y estado activo de un funcionario al asignar caja. | orders para caja; Auth para comprobar cuenta y versión. | Nuevo; pendiente. |

#### inventory

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| I04 | `POST /interno/catalogo/consultas` | Consultar en lote productos/combos por sus IDs; devuelve campos públicos o precios autorizados según consumidor y contexto. | orders para precios; GraphQL Gateway para catálogo público. El lote tiene un máximo. | Nuevo; pendiente. |
| I05 | `POST /interno/reservas` | Reservar todos los ítems del checkout o rechazar todo; resolver componentes de combos y fijar vencimiento de 15 minutos con reloj del servidor. | orders; referencia de operación e identidad verificadas. | Nuevo; pendiente. |
| I06 | `GET /interno/reservas/{id}` | Consultar estado y vencimiento para recuperar o conciliar una operación. | orders; solo reservas vinculadas a operaciones bajo su autoridad. | Nuevo; pendiente. |
| I07 | `POST /interno/reservas/{id}/consumos` | Consumir una reserva válida una sola vez, resolviendo la carrera contra el vencimiento. | orders, después de recibir un pago verificado. | Nuevo; pendiente. |
| I08 | `POST /interno/reservas/{id}/liberaciones` | Liberar reserva activa al cancelar o vencer; no repone unidades ya consumidas. | orders o proceso de vencimiento autorizado. | Nuevo; pendiente. |
| I09 | `POST /interno/reservas/{id}/restituciones` | Reponer una vez unidades de una reserva consumida cuando se cancela antes de preparar; nunca en reembolso excepcional. | orders; operación de cancelación autorizada. | Nuevo; pendiente. |

#### orders

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| I10 | `GET /interno/ordenes/{id}/cobro` | Obtener total oficial, moneda, propietario, caja y estado/vigencia mínimos para cobrar o evaluar devolución. | payments; identidad técnica y contexto de operación autorizados. | Nuevo; pendiente. |
| I11 | `POST /interno/ordenes/{id}/resultados-pago` | Registrar resultado verificado. Si se aprueba y la reserva puede consumirse, avanzar pedido y registrar venta una vez; si llega tarde/cancelado, coordinar devolución. | payments; referencia del intento, evento, monto y moneda comprobados. | Nuevo; pendiente. |
| I12 | `POST /interno/ordenes/{id}/vencimientos` | Resolver expiración con reloj del servidor, estado pendiente y resultado de la reserva; no expirar pedidos ya pagados. | Proceso interno de vencimiento autorizado. | Nuevo; pendiente. |
| I13 | `POST /interno/ordenes/{id}/resultados-reembolso` | Registrar resultado financiero e historial de la devolución según su causa, conservando la trazabilidad del pedido. | payments; resultado verificado de devolución. | Nuevo; pendiente. |
| I18 | `POST /interno/ordenes/{id}/autorizaciones-reembolso` | Validar la aprobación excepcional: si sigue preparando, cancelar con causa administrativa sin restituir stock; enviado/entregado sigue igual. Idempotente por decisión. | payments con identidad técnica y contexto de Administrador verificado. | Nuevo; pendiente. |

GraphQL consulta S21 `GET /ordenes`, S22 `GET /ordenes/{id}` y S30 `GET /reportes/ventas` por la red privada con su identidad de servicio y la del usuario. Se reutilizan esos contratos y sus controles; no se leen tablas ajenas. Orders aporta los datos históricos de comprador/dirección conservados en el pedido; no se consulta clients por cada fila del listado.

#### payments

| ID | Método y ruta | Propósito | Acceso permitido | Estado en diagnóstico del 24 oct. |
| --- | --- | --- | --- | --- |
| I14 | `POST /interno/reembolsos` | Ejecutar devolución por cancelación pagada o cobro tardío, validando causa, pago y monto aún no devuelto. Las aprobaciones excepcionales usan la misma lógica financiera dentro de payments. | orders para causas automáticas autorizadas; sin permiso para simular una aprobación excepcional de Administrador. | Nuevo; pendiente. |
| I15 | `GET /interno/pagos/{id}/estado` | Consultar estado financiero verificado para recuperar o conciliar una operación sin repetir el cobro. | orders; pago asociado a un pedido autorizado. | Nuevo; pendiente. |
| I16 | `POST /interno/pagos/consultas` | Consultar por lote acotado de pedido_ids los resúmenes verificados de pagos/devoluciones, sin iniciar cobros ni modificar datos. Evita una llamada por cada pedido. | GraphQL con identidad técnica y contexto verificado: Cliente propietario; Administrador; Cajero de su caja para campos financieros permitidos. Cada pedido se autoriza y solo se devuelven campos mínimos; sin payloads del proveedor. | Nuevo; pendiente. |
| I17 | `GET /interno/reportes/movimientos` | Obtener indicadores agregados de cobros y devoluciones verificados para desde/hasta. Payments calcula sus indicadores y documenta período/corte, sin alterar ventas ni dar acceso a pagos individuales. | GraphQL con identidad técnica y contexto de Administrador o Dueño; finalidad de reporte y datos personales mínimos. | Nuevo; pendiente. |

### Reglas comunes de los contratos

- En creaciones y operaciones con efectos repetibles se define `Idempotency-Key`, asociada al actor/servicio, operación y contenido. Repetir la misma solicitud devuelve el resultado registrado; una clave con contenido diferente genera conflicto. Una nueva intención de reintentar un pago rechazado usa otra clave y otro intento.
- Los callbacks se deduplican además por proveedor y evento/transacción. Si dos intentos distintos terminan cobrados, se registra el excedente y se concilia/devolverá sin crear otra venta ni consumir de nuevo.
- Cada transición vuelve a comprobar estado/versión al guardar. Entre cancelar e iniciar preparación gana la primera operación confirmada. No hay prioridad especial: cancelar primero impide preparar; preparar primero cierra la cancelación normal.
- Las operaciones entre servicios usan identificadores de correlación, tiempos de espera y recuperación por referencia/clave idempotente. Un timeout no demuestra que el destino no ejecutó la operación: consultar o reintentar con la misma clave antes de compensar, sin duplicar efectos.
- Propuesta de errores: 401 por sesión ausente/vencida en rutas protegidas; 403 por rol o identidad técnica insuficiente; 404 por recurso inexistente o pedido ajeno; 409 por stock/estado/versión/conflicto de idempotencia; 422 por campos inválidos; errores controlados por dependencia no disponible.
- Los estados operativos canónicos son pendiente, pagado, preparando, enviado, entregado, cancelado y expirado. Pagos: pendiente/aprobado/rechazado; solicitudes: pendiente/aprobada/rechazada; devoluciones: pendiente/completado/fallido. Reembolsado no es estado operativo. El backend nuevo usa estos estados; migrar registros históricos con pagada/enviada/entregada/cancelada sigue pendiente si se importa la base anterior.
- Cada servicio incorpora `GET /health` para supervisión con datos mínimos; hoy existe en el API Gateway y queda pendiente en los servicios nuevos. Los chequeos privados no se publican como rutas de negocio. Vault conserva su API propia para consumidores internos autorizados.
- Los detalles están en [contratos-rest.md](contratos-rest.md) y [contratos-graphql.md](contratos-graphql.md). Aún se requieren trazabilidad formal a requisitos/pantallas, UML, implementación, configuración y evidencia para cerrar M1/M6/M8; el catálogo no acredita pruebas ejecutadas.

---

## Carrito

**Representa la selección provisional de productos del cliente y es una entidad separada del pedido. No utiliza los estados del pedido.**

- En su estado inicial se encuentra vació. El cliente puede agregar productos, quitarlos y modificar sus cantidades antes de confirmar el checkout.
- Agregar o modificar productos en el carrito no crea un pedido ni reserva stock. La disponibilidad de sus productos puede cambiar mientras el cliente elige.
- Los precios y el total mostrados en el carrito son estimaciones. Al confirmar el checkout, el servidor valida los productos, las cantidades y la disponibilidad, y calcula el total vigente.
- Si no puede aceptar la compra, informa qué debe corregirse y conserva la selección del carrito para que el cliente pueda modificarla.
- El pedido conserva una copia de los productos, cantidades y precios aceptados. Modificar el carrito después no modifica ese pedido.
- El vencimiento de un pedido no elimina el carrito ni el historial del pedido. Confirmar nuevamente el checkout crea otro pedido y una nueva reserva, sujetos a validación de disponibilidad y precios.

---

## Estados de pedido

El estado operativo describe preparación/entrega; el dinero tiene estados independientes.

| Estado | Qué garantiza |
| --- | --- |
| `pendiente` | Checkout aceptado con reserva completa durante 15 minutos; espera pago. |
| `pagado` | Pago verificado, reserva consumida y venta registrada una vez. |
| `preparando` | Despacho inició preparación desde pagado; se cierra la cancelación normal. |
| `enviado` | Salió a reparto. Un reembolso excepcional no detiene la entrega. |
| `entregado` | Entrega confirmada; conserva estado aunque se devuelva el dinero. |
| `cancelado` | Cancelación normal antes de preparar o interrupción excepcional durante preparación. Conservar causa, estado anterior, actor, motivo y fecha. |
| `expirado` | Venció la reserva sin consumo válido. Conservar pedido, liberar unidades y devolver un cobro tardío sin reactivarlo. |

Por ejemplo, un pedido entregado puede tener una devolución completada. El estado final por sí solo no decide restitución ni reembolso.

---

## Transiciones y permisos

### Transiciones de pedido

| Transición | Actor | Comprobaciones y efectos |
| --- | --- | --- |
| Checkout → pendiente | Cliente con sesión y correo verificado | Caja/cajero habilitados, comuna/tarifa oficial, reserva íntegra y snapshots. |
| pendiente → pagado | Identidad técnica de payments | Pago, monto, moneda y consumo válidos; venta y comprobante únicos. |
| pagado → preparando | Despacho | Versión/estado vigentes y sin cancelación aceptada; registrar responsable/fecha. |
| preparando → enviado | Despacho | Pedido preparado y salida confirmada. |
| enviado → entregado | Despacho | Entrega confirmada. |
| pendiente → cancelado | Cliente propietario o Administrador | Motivo; liberar reserva no consumida. Si un cobro/consumo concurrente ya ocurrió, conciliar y devolver/restituir lo que corresponda. |
| pagado → cancelado | Cliente propietario o Administrador | Antes de preparar, con motivo; restituir stock y solicitar devolución completa una vez. |
| pendiente → expirado | Proceso interno autorizado | Reloj del servidor y reserva vencida/liberada. Si el consumo válido ya ganó la carrera, conciliarlo sin expirar erróneamente. |
| preparando → cancelado | Administrador aprueba; payments coordina I18 con orders | Solicitud/pago/motivo válidos. Detener preparación sin recuperar stock y devolver el saldo íntegro. |
| enviado/entregado → mismo estado | Administrador aprueba la excepción | Devolver todo el saldo sin recuperar stock. Enviado sigue hasta entrega. |

La carrera cancelar/preparar se resuelve atómicamente por versión/estado: gana la primera confirmada. La aprobación excepcional vuelve a leer el estado: si el envío ya se confirmó, continúa. Las referencias para un reintento explícito se conservan aparte, sin inventar estados operativos públicos.

### Actores y permisos

| Actor | Descripción | Alcance | Restricciones |
| --- | --- | --- | --- | 
| Visitante | Usuario sin sesión activa | Catálogo público, gestionar carrito | Crear y/o actualizar pedidos, cambiar estados, ver datos privados, iniciar reembolsos |
| Cliente | Usuario con cuenta y sesión activas | Crear, consultar, cancelar pedidos, solicitar reembolso | Pedidos y datos ajenos, preparación, despacho, confirmación de pago, autorización de reembolsos |
| Administrador | Encargado de administración del sistema | Administrar usuarios, clientes, productos. Consultar, anular, autorizar reembolso de pedidos y reintentar devoluciones fallidas | Debe respetar transiciones. Confirmación de pagos sin verificación |
| Cajero virtual |  Encargado de ventas web | Gestion de su caja, operaciones de pago, emisión y envío de comprobantes  | No puede aprobar pago, autorizar reembolsos ni operar otras cajas sin permiso |
| Despacho | Personal encargado de coordinar la preparación y entrega | Consultar pedidos pagados, imprimir órdenes para cocina y registrar preparación, salida y entrega | No puede preparar pedidos sin pago confirmado, gestionar reembolsos ni consultar datos personales sin finalidad de despacho |
| Dueño |  Responsable del negocio | Consulta de reportes de ventas, administración de productos  | No obtiene permisos de administrador ni acceso irrestricto a datos personales |
| Identidad técnica |  Servicio autenticado | Operaciones internas como notificación de pagos verificados y vencimiento de reservas | Permisos se limitan a operaciones autorizadas. No recibe acceso general del sistema |


---

## Reservas y stock

- La reserva empieza al confirmar checkout y dura 15 minutos con reloj del servidor, sin extensión por reintentos.
- Inventory acepta todos los ítems o ninguno, incluyendo componentes de combos. Devuelve reserva y nombres/precios oficiales para los snapshots de orders.
- El pago solo avanza el pedido cuando se confirma consumo válido. Inventory resuelve consumo/vencimiento una vez; al llegar al límite no se acepta consumo nuevo.
- Cancelar/vencer antes de consumir libera reserva. Cancelar normalmente después del pago y antes de preparar restituye stock. La excepción durante preparación no lo restituye.
- Las operaciones conservan referencia/idempotencia; ante timeout se consulta antes de compensar. No se repiten stock, venta, comprobante ni devolución.
- Stock no puede editarse por debajo de lo reservado. Desactivar afecta nuevas compras/combos, sin borrar compromisos e historial aceptados.

---

## Cancelaciones y reembolsos

### Cancelación normal

Cliente propietario o Administrador pueden cancelar pendiente/pagado, con motivo, antes de preparar. Pendiente libera reserva; pagado restituye stock y solicita devolución completa. Cancelado se conserva aunque falle la devolución: el dinero se resuelve por separado.

### Solicitud excepcional

Cliente puede solicitarla desde preparando/enviado/entregado, con motivo y antecedentes solo textuales. Sin imágenes, archivos ni enlaces obligatorios. Una solicitud/proceso activo por pedido; tras rechazo se admite otra con nuevos antecedentes. Un saldo íntegramente devuelto no se devuelve de nuevo.

Administrador aprueba/rechaza con razón. Al aprobar, orders cancela si aún está preparando; si está enviado/entregado conserva recorrido. No se recupera stock. Se devuelve todo el saldo verificado sin importes parciales elegidos por usuarios.

### Estados financieros y recuperación

- Intento: pendiente/aprobado/rechazado. Rechazo permite otro intento con reserva vigente. Payments resume el cobro aprobado o, si no existe, el intento más reciente.
- Solicitud: pendiente/aprobada/rechazada. Aprobada no significa que el dinero ya se devolvió.
- Devolución: pendiente/completado/fallido. Un resultado incierto queda pendiente de conciliación, sin otra devolución a ciegas.
- Administrador reintenta/reconcilia con S42, conservando autorización, causa y referencia, sin nueva aprobación ni efectos repetidos de stock/pedido. No hay reintentos financieros automáticos programados.
- Cancelación pagada, pago tardío y cobro duplicado originan devoluciones técnicas autorizadas sin exigir una solicitud excepcional del Cliente.

---

## Despacho, caja, comprobantes y reportes

### Cobertura y tarifas

Comunas permitidas con tarifa fija, sin radio, geocodificación o costo por kilómetro. Orders administra la referencia, expone S06 y rechaza comunas fuera de cobertura. Clients reutiliza S06 para sus formularios/validación y conserva la etiqueta necesaria del perfil; no administra tarifas. No se añade mantenedor de comunas.

El navegador estima; el servidor fija y guarda el costo en checkout. Cambiar tarifas no modifica pedidos previos. Es la adaptación acordada frente al envío gratuito en 3 km del caso de referencia.

### Caja y comprobantes

Una única caja Web con cajero habilitado asignado por Administrador. Opera aunque el cajero no esté conectado, sin apertura/cierre manual. Nuevas compras requieren configuración válida; transacciones ya iniciadas se concilian con sus referencias históricas.

La venta genera automáticamente un comprobante único y solicita correo simulado al destinatario verificado. Cajero de la caja puede reintentar emisión/envío fallidos. Cola de preparación por confirmación de pago ascendente e ID; descargar/imprimir no inicia preparación.

### Reporte básico

Administrador/Dueño: listado paginado, cantidad de ventas, total cobrado, total devuelto y neto cobrado por período. Sin rankings ni desglose por producto/día.

Filas de ventas por fecha de registro; cada cobro/devolución por su propia fecha verificada. El total de filas puede diferir de los movimientos financieros y el neto puede ser negativo. Una devolución del martes no cambia el reporte del lunes. Desde/hasta se interpretan como días de America/Santiago, incluyendo ambos mediante un límite exclusivo al iniciar el siguiente; timestamps en UTC y conversiones según la zona, no un desfase horario fijo.

---

## Sesiones y límites de acceso

- Auth separado: sesión opaca hasheada en su propio SQLite, ocho horas fijas; sessionStorage y Authorization: Bearer; logout revoca inmediatamente. Sin migración a cookies.
- Se verifican cuenta y permisos actuales. Cambios de clave/rol/desactivación invalidan sesiones afectadas. No se confía en roles/identidad enviados en formularios.
- El token personal accesible a JavaScript exige evitar inserciones inseguras y no registrarlo en logs. Secretos de integración de Vault nunca van en bundle/respuestas del navegador.
- GraphQL: profundidad 6; costo estimado 2000 puntos; ejecución máxima de 10 s y llamadas privadas de hasta 3 s. Campos, listas y aliases cuentan; las lecturas se agrupan por página o pedido, sin caché de tareas.
- Gateway: 60 solicitudes/min por usuario; 120/min por IP anónima. Tras cinco fallos de login en el minuto fijo actual, bloquear temporalmente nuevos intentos desde esa IP. Responder 429 con Retry-After; llamadas privadas no consumen de nuevo el cupo externo.
- Páginas máximas de 50: 12 por defecto en catálogo, 20 en otros listados. Filtros antes de contar/paginar y orden estable.
- Fallo de enriquecimiento: datos parciales autorizados y errors por campo; no convertir en vacío, pago rechazado, cero devuelto o agotado.
- Estos límites se comprobaron funcionalmente; no constituyen una medición de capacidad. Son constantes simples para la demostración local.

---

## Escenarios de comprobación

1. Carrito sin reserva; checkout con reserva íntegra por 15 min, snapshots y tarifa oficial.
2. Última unidad/combos concurrentes: aceptación completa o rechazo sin reservas parciales.
3. Rechazo/reintento sin extensión; eventos repetidos sin doble venta/stock/comprobante.
4. Pago con reserva vencida/cancelada: mantener expirado/cancelado, devolver y no preparar.
5. Cancelación pagada normal: stock restituido una vez y devolución completa independiente.
6. Cancelar/preparar simultáneamente: solo gana la primera confirmada.
7. Excepción durante preparación: cancelado sin restituir stock; si el envío ganó, completar entrega.
8. Rechazo admite nuevos antecedentes; una activa. Fallo de devolución se reintenta manualmente sin duplicar dinero.
9. Comuna no habilitada/costo manipulado: validar/calcular en servidor; tarifa cambiada no reescribe historia.
10. Producto desactivado fuera del catálogo y combos no disponibles, con historia intacta.
11. Sesión vencida/cuenta desactivada/pedido ajeno rechazados; Despacho sin importes y Dueño sin acceso general.
12. Dependencia caída con respuesta parcial; profundidad/costo/página/frecuencia excesivos rechazados.
13. Venta lunes/devolución martes: movimientos por fecha propia, neto correcto sin doble descuento.
14. Simulador aprobado/rechazado/pendiente, eventos tardíos/repetidos y fallo/reintento financiero; correo identificado como simulado.

UML completos y matrices formales siguen pendientes. La implementación y sus pruebas nuevas se registran en [estado-backend-e2.md](estado-backend-e2.md); el despliegue con Docker/Vault real queda por verificar. Analítica/gRPC se justificarán con necesidades y mediciones de M9; los acuerdos no acreditan aplicabilidad ni rendimiento.
