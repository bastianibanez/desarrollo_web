# Evaluación 2 · Fit Express · Caso 19

Fecha: 9 de noviembre de 2026. Integrantes: pendientes de completar por el equipo.

Versión funcional de referencia: demo estática del PR #16, integrada en `068f0a3`. La limpieza documental no cambia la lógica de negocio. Las evidencias indican el árbol de código validado, sin confundirlo con el commit de publicación del informe.

## Alcance y brechas

El backend usa servicios separados, HTTP privado, Auth, Vault y agregación GraphQL. El frontend es una demo estática con sesión ficticia y datos locales: no autentica contra Auth, no consulta GraphQL y no ejecuta compras reales. No se declara cumplida la integración completa con frontend de los módulos 8 y 10.

Correo y pagos son simulados. No hay proveedor financiero ni correo externo real. Falta completar integrantes y acreditar una interfaz real conectada al backend si se exige el logro completo de esos módulos.

## Entregables por módulo

| Módulo | Evidencia |
| --- | --- |
| 1. Servicios y trazabilidad | Matriz de requisitos de este informe y [contratos REST](contratos-rest.md). |
| 2. UML y límites | [Dominio](modelo-dominio.mmd), [servicios](diagramas/dominio-servicios.mmd), [cardinalidades](modelo-datos.md). |
| 3. Sistemas e integración | Matriz de sistemas, [componentes](diagramas/componentes.mmd) y [secuencia](diagramas/checkout.mmd). |
| 4. Stakeholders y permisos | Registro de actores y matriz de permisos de este informe. |
| 5. Gateway y políticas | [UML gateway](diagramas/gateway.mmd) y fronteras explicadas aquí. |
| 6. Rutas e identidades | Matriz de rutas, inventario simbólico y [GraphQL](contratos-graphql.md). |
| 7. Protección de datos | Clasificación, custodia y pruebas referenciadas aquí. |
| 8. GraphQL | [Schema](../services/graphql/schema.graphql), resolvers, contratos y pruebas; frontend sin integración. |
| 9. Analítica y gRPC | [ADR y carga](adr-001-rest-analitica.md). |
| 10. Implementación | [Arranque](../README.md), [evidencias](evidencias/README.md) y pruebas; frontend de demostración. |

El mapa de componentes y la secuencia describen el backend y sus consumidores HTTP de prueba. El frontend actual se sirve por Vite o Nginx en el puerto 5173, sin llamadas al gateway. Cada UML Mermaid tiene un SVG con el mismo nombre. El [C4 de la clase](structurizr/README.md) se conserva como fuente y vistas complementarias del mapa de sistemas.

## Sistemas, autoridad y fallos

| Sistema / naturaleza | Datos propios y autoridad | Integraciones / fallo |
| --- | --- | --- |
| auth / seguridad | Sesiones, expiración y revocación | clients valida cuenta vigente; sin respuesta no acepta sesión |
| clients / transaccional | Perfiles, cuentas, hash, roles y verificación | orders provee comunas; error controlado si no responde |
| inventory / transaccional | Productos, combos, stock, reservas | No lee bases ajenas; reserva completa o rechazo, nunca parcial |
| orders / transaccional | Pedidos, estados, snapshots, cajas, ventas y comprobantes | clients valida perfil/cajero; inventory reserva/consume/libera; payments devuelve. Reintentar con misma clave si se interrumpe |
| payments / transaccional | Intentos, resultados verificados, solicitudes y reembolsos | orders autoriza importe/propiedad; simulador confirma pago. Avisos deduplicados, devolución conciliable |
| GraphQL / agregación | Sin base de negocio; seis queries | APIs privadas; error parcial en campos opcionales, sin reemplazar historial por catálogo actual |
| gateway / frontera | Rutas y contadores por minuto en memoria | auth introspecta; destinos explícitos. 503 por dependencia inaccesible |
| simulator / adaptador de prueba | Cobros y devoluciones del proveedor ficticio | HMAC y aviso a payments; reenvío explícito ante fallo |
| Vault / secretos | Identidades técnicas por servicio | Sin secretos disponibles falla arranque; no hay fallback incrustado |

Todas las conexiones están enumeradas en la matriz de identidades. SQLite no tiene claves foráneas distribuidas: un identificador externo es una referencia validada por API. No hay transacción global; la idempotencia permite continuar operaciones interrumpidas. La tarea de vencimiento es la única recuperación periódica.

## Stakeholders

| Parte interesada | Rol y finalidad |
| --- | --- |
| Comprador | Cliente: cuenta y pedidos propios, pagos y solicitudes |
| Administrador del local | Administrador: clientes, funcionarios, caja y decisiones excepcionales |
| Cajero | Cajero: cobros y comprobantes de su caja |
| Cocina/reparto | Despacho: preparación, envío y entrega; campos operativos |
| Propietario del negocio | Dueño (`dueno`): catálogo y reporte financiero |
| Visitante | Sin sesión: catálogo público y registro |
| Docente/evaluador | Sin permisos operativos por defecto; recibe código, diagramas y evidencias |
| Destinatario del comprobante | Recibe documento por correo simulado; no obtiene rol adicional |
| Proveedor de pagos | Identidad técnica, no funcionario; firma y conciliación de resultados |

## Trazabilidad de requisitos y pantallas

Las pantallas siguientes son maquetas; la tabla relaciona requisitos con contratos backend, no acredita consumo desde la interfaz. Los IDs R/P son del informe. Los S/G son los de contratos; los contratos corresponden al backend y se ejercitan con clientes HTTP de prueba. Las pruebas se encuentran en `services/tests/test_backend.py`, salvo indicación distinta. Resultados ejecutados: [evidencias](evidencias/README.md).

| Requisito | Pantalla existente / brecha | Operaciones | Prueba principal |
| --- | --- | --- | --- |
| R01 Identificarse, salir y verificar correo | P01 `acceso.html`, P02 `confirmar.html` | S01–S05 / G04 | `test_register_verify_and_login`, `test_session_revoked_on_role_edit` |
| R02 Catálogo, ofertas y combos | P03 `index.html` | G03; S13–S19 | `test_catalog_and_private_boundary`, `test_combo_and_product_demand_is_atomic` |
| R03 Compra con entrega y stock oficial | P04 `carrito.html` | S06, S20 | `test_checkout_idempotency_and_ownership`, `test_last_unit_concurrent_checkouts` |
| R04 Cobro verificado y comprobante | P04 y retorno de proveedor pendiente de migración | S28–S35, S36 | `test_payment_sale_receipt_and_dispatch`, `test_forged_payment_notice_cannot_confirm_payment` |
| R05 Historial propio y cancelaciones | P05 `cuenta.html`; ampliar seguimiento | G01, G02, S23 | `test_paid_cancellation_restores_and_refunds_once`, `test_unpaid_cancellation_releases_without_adding_stock` |
| R06 Administración de perfiles e inventario | P06 `panel.html` | S07–S12, S17–S19, S29 | `test_session_revoked_on_role_edit`, `test_product_deactivation_preserves_accepted_reservation` |
| R07 Cocina y despacho | P06; incorporar cola y documento | G05, S24–S27 | `test_cancel_prepare_race_has_single_winner`, `test_despacho_field_permissions_and_owner_scope` |
| R08 Devolución excepcional | P05/P06; formularios pendientes | S37–S40, S42 | `test_exceptional_refund_respects_operational_stage`, `test_lost_refund_response_reconciles_same_provider_operation` |
| R09 Reportes por período | P06; migrar consulta | G06 / S30 | `test_report_negative_net_uses_movement_dates` |
| R10 Frontera segura y errores controlados | Todas | S41, I01, rutas explícitas | `test_graphql_limits_and_finance_batching`, `test_gateway_ignores_browser_identity_headers_and_uses_auth` |
| R11 Recorrido backend completo | Consumidor HTTP de prueba | Checkout → pago → entrega | `test_tcp.py::test_complete_backend_over_real_http` |
| R12 Correlación sin secretos | Operación técnica | Todas las APIs Python | `test_observability.py` |

## Lectura de UML y fronteras

`--` es asociación con multiplicidades en ambos extremos; `*--` es composición; `..>` es dependencia de uso, sin cardinalidad entre registros. `REF` denota referencia entre sistemas, sin FK distribuida. Las interfaces `«service»` agrupan los handlers funcionales del profesor; no afirman que existan esas clases Python. Las operaciones agrupadas S07–S09, por ejemplo, corresponden a las tres operaciones individualizadas en contratos.

Cada pedido confirmado tiene una o más líneas y una reserva; antes de completar checkout puede existir un registro técnico incompleto que no se presenta como compra confirmada. Un cliente puede tener varios pedidos; cada pedido varios intentos de pago, como máximo una venta aceptada y un comprobante por venta. Un pago puede tener un proceso de reembolso con múltiples intentos. La cuenta del funcionario no tiene Cliente; las sesiones viven en auth y refieren a la cuenta de clients. El detalle de combos, reservas, historial y caja está en el dominio completo.

El UML del gateway contiene 36 definiciones (34 propias y dos del simulador), un limitador compartido por instancia y un contexto técnico. Los resolvers usan un contexto de usuario por solicitud. Las flechas HTTP del mapa de componentes representan comunicación, no asociaciones entre registros. Los ocho componentes cargan su identidad de Vault aunque el mapa muestre una sola flecha explicativa para evitar cruces.

Solicitud permitida: Bearer → introspección → rol en ruta → cabeceras reconstruidas → secreto del llamador → propiedad y estado en negocio. Solicitud denegada: Cliente intenta crear producto → gateway devuelve 403; conocer la URL privada no ayuda porque no hay puerto publicado y el backend exige secreto. En GraphQL un rol Despacho puede consultar estado/dirección operativa pero no los campos financieros: el resolver devuelve error por campo sin elevar permisos.

## Reglas de negocio

- El carrito no reserva stock. Checkout reserva todos los componentes de la compra durante 15 minutos con precios oficiales.
- Los combos comparten stock con sus productos; una reserva insuficiente se rechaza completa.
- El pedido conserva snapshots de comprador, dirección, líneas y precios.
- El pago debe verificarse con el proveedor; avisos duplicados no duplican venta, stock ni comprobante.
- Antes de preparar, Cliente propietario o Administrador pueden cancelar. Pendiente libera reserva; pagado restituye stock y solicita devolución.
- Una devolución excepcional requiere solicitud del Cliente y decisión del Administrador. Si el pedido está preparando se detiene; enviado/entregado conserva su recorrido. No se repone stock por esa excepción.
- Despacho realiza pagado → preparando → enviado → entregado. Pago y devolución tienen estados financieros separados.
- Los reintentos conservan la clave de idempotencia; no existe transacción SQL distribuida ni recuperación automática de pagos. El vencimiento de reservas sí tiene una tarea periódica.

## Matriz de rutas y permisos

Corresponde a `services/gateway/routes.py`. S01–S42 conservan los IDs de los contratos. Las rutas S privadas se consumen desde GraphQL y no se publican por REST. Solo el verbo indicado está permitido: otros verbos no registrados son no aplicables (405); rutas no registradas, 404. Un rol no listado recibe 403; una ruta protegida sin sesión, 401. Las condiciones de propiedad y estado se vuelven a verificar en el destino.

| ID | Verbo | Ruta externa | Destino privado | Roles permitidos | Credencial técnica |
| --- | --- | --- | --- | --- | --- |
| S01 | POST | `/api/login` | auth: `/login` | Anónimo | `gateway → auth` |
| S02 | POST | `/api/logout` | auth: `/logout` | cliente, administrador, cajero, despacho, dueno | `gateway → auth` |
| S04 | POST | `/api/registro` | clients: `/registro` | Anónimo | `gateway → clients` |
| S05 | POST | `/api/clientes/verificar-correo` | clients: `/clientes/verificar-correo` | Anónimo | `gateway → clients` |
| S07 | GET | `/api/admin/clientes` | clients: `/admin/clientes` | administrador | `gateway → clients` |
| S08 | POST | `/api/admin/clientes` | clients: `/admin/clientes` | administrador | `gateway → clients` |
| S09 | PATCH | `/api/admin/clientes/{id}` | clients: `/admin/clientes/{id}` | administrador | `gateway → clients` |
| S10 | GET | `/api/admin/usuarios` | clients: `/admin/usuarios` | administrador | `gateway → clients` |
| S11 | POST | `/api/admin/usuarios` | clients: `/admin/usuarios` | administrador | `gateway → clients` |
| S12 | PATCH | `/api/admin/usuarios/{id}` | clients: `/admin/usuarios/{id}` | administrador | `gateway → clients` |
| S17 | POST | `/api/productos` | inventory: `/productos` | administrador, dueno | `gateway → inventory` |
| S18 | PUT | `/api/productos/{id}` | inventory: `/productos/{id}` | administrador, dueno | `gateway → inventory` |
| S19 | DELETE | `/api/productos/{id}` | inventory: `/productos/{id}` | administrador, dueno | `gateway → inventory` |
| S06 | GET | `/api/comunas` | orders: `/comunas` | Anónimo | `gateway → orders` |
| S20 | POST | `/api/ordenes` | orders: `/ordenes` | cliente | `gateway → orders` |
| S23 | POST | `/api/ordenes/{id}/cancelaciones` | orders: `/ordenes/{id}/cancelaciones` | cliente, administrador | `gateway → orders` |
| S24 | POST | `/api/ordenes/{id}/preparacion` | orders: `/ordenes/{id}/preparacion` | despacho | `gateway → orders` |
| S25 | POST | `/api/ordenes/{id}/envios` | orders: `/ordenes/{id}/envios` | despacho | `gateway → orders` |
| S26 | POST | `/api/ordenes/{id}/entregas` | orders: `/ordenes/{id}/entregas` | despacho | `gateway → orders` |
| S27 | GET | `/api/ordenes/{id}/orden-despacho` | orders: `/ordenes/{id}/orden-despacho` | despacho | `gateway → orders` |
| S28 | GET | `/api/cajas` | orders: `/cajas` | administrador, cajero | `gateway → orders` |
| S29 | PATCH | `/api/cajas/{id}` | orders: `/cajas/{id}` | administrador | `gateway → orders` |
| S31 | POST | `/api/ventas/{id}/comprobantes` | orders: `/ventas/{id}/comprobantes` | cajero | `gateway → orders` |
| S32 | GET | `/api/ventas/{id}/comprobante` | orders: `/ventas/{id}/comprobante` | cliente, cajero, administrador | `gateway → orders` |
| S33 | POST | `/api/ventas/{id}/comprobante/envios` | orders: `/ventas/{id}/comprobante/envios` | cajero | `gateway → orders` |
| S34 | POST | `/api/pagos` | payments: `/pagos` | cliente, cajero | `gateway → payments` |
| S35 | GET | `/api/pagos/{id}` | payments: `/pagos/{id}` | cliente, cajero, administrador | `gateway → payments` |
| S36 | POST | `/api/webhooks/pagos/{proveedor}` | payments: `/webhooks/pagos/{proveedor}` | Sin Bearer; firma HMAC y conciliación obligatorias | `gateway → payments` |
| S37 | POST | `/api/solicitudes-reembolso` | payments: `/solicitudes-reembolso` | cliente | `gateway → payments` |
| S38 | GET | `/api/solicitudes-reembolso` | payments: `/solicitudes-reembolso` | cliente, administrador | `gateway → payments` |
| S39 | GET | `/api/solicitudes-reembolso/{id}` | payments: `/solicitudes-reembolso/{id}` | cliente, administrador | `gateway → payments` |
| S40 | POST | `/api/solicitudes-reembolso/{id}/decisiones` | payments: `/solicitudes-reembolso/{id}/decisiones` | administrador | `gateway → payments` |
| S42 | POST | `/api/reembolsos/{id}/reintentos` | payments: `/reembolsos/{id}/reintentos` | administrador | `gateway → payments` |
| S41 | POST | `/api/graphql` | graphql: `/graphql` | Catálogo anónimo; resto por operación/campo (G01–G06) | `gateway → graphql` |
| Demo | GET | `/simulador/pagos/checkout/{token}` | simulator: `/checkout/{token}` | Token opaco del checkout (demostración) | `gateway → simulator` |
| Demo | POST | `/simulador/pagos/checkout/{token}/resultado` | simulator: `/checkout/{token}/resultado` | Token opaco del checkout (demostración) | `gateway → simulator` |

### Ámbito y comprobación

| Familia | Restricción adicional en backend |
| --- | --- |
| Pedidos, pagos y comprobantes del Cliente | Propiedad obtenida de identidad verificada, nunca cliente_id del cuerpo |
| Cajero | Caja asignada y actor histórico según operación |
| Despacho | Transiciones válidas; GraphQL oculta importes y pagos |
| Reembolsos | Cliente crea solicitud propia; Administrador decide; estado operativo validado por orders |
| Productos | Administrador/Dueño; DELETE desactiva y conserva historial |
| GraphQL | Ver [contratos por operación y campo](contratos-graphql.md); POST no concede acceso global |

### Identidades técnicas (no roles humanos)

Cada flecha tiene un secreto distinto, custodiado como `secret/data/services/{origen}.outgoing.{destino}` y `secret/data/services/{destino}.incoming.{origen}`. `bootstrap.py` crea solo estas conexiones; cada endpoint además limita llamadores con `require_caller`.

| Consumidor | Destinos autorizados |
| --- | --- |
| gateway | auth, clients, graphql, inventory, orders, payments, simulator |
| auth | clients |
| clients | orders |
| inventory | Ninguno |
| orders | clients, inventory, orders, payments |
| payments | orders, simulator |
| graphql | clients, inventory, orders, payments |
| simulator | payments |

## Datos, sesiones y secretos

Política para la demostración académica local con datos ficticios. No se declara retención legal de producción ni cifrado de SQLite que el código no implemente.

| Dato | Finalidad / clasificación | Custodio | Acceso y representación | Protección / retención real |
| --- | --- | --- | --- | --- |
| Nombre/descripción/precio de producto | Selección / público | inventory | Catálogo; stock numérico solo personal autorizado | DTO; desactivar no elimina compras |
| RUN, correo, nombre, teléfono | Registro/contacto / personal restringido | clients | Titular y administración; campos mínimos por contrato | APIs privadas y autorización; persiste hasta gestión manual de la demo |
| Fecha nacimiento/sexo/dirección de perfil | Campos del perfil heredado / restringido | clients | Perfil propio/administración; nunca catálogo | Opcionales según DTO; no se utilizan para autorizar pagos |
| Dirección y comprador históricos | Cumplir entrega / restringido | orders | Propietario y roles operativos según campo | Snapshot conserva evidencia de compra, sin purga automática |
| Pagos, ventas y devoluciones | Conciliación / financiero restringido | payments / orders | Titular, cajero de su caja, administración; dueño solo reporte | Unicidad/idempotencia; historial persistente de demo |
| Contraseña | Autenticación / credencial | clients | Solo entrada; jamás devuelta | PBKDF2-SHA256, 600000 iteraciones, sal aleatoria de 16 bytes; hash hasta reemplazo/desactivación |
| Código de verificación | Prueba de correo / credencial temporal | clients | Solo destinatario en correo simulado | Hash, vencimiento e intentos; mensajes de demo contienen código y requieren acceso local restringido |
| Bearer | Sesión personal / secreto del cliente | auth | Devuelto una vez en login; el consumidor lo presenta | Token aleatorio; hash SHA256 en SQLite; ocho horas; logout elimina sesión; cambio de versión de cuenta invalida |
| Token opaco de checkout | Acceso a pantalla simulada / capacidad temporal | simulator | URL al comprador | No se registra URL cruda; persiste ligado a la operación, sin limpieza automática |
| Secretos técnicos/HMAC | Autenticar integración / secreto del comercio | Vault | Nunca frontend ni DTO público | Alcance por arista o proveedor; lectura al arrancar |

**Sí se custodian credenciales asociadas al cliente**: hash de contraseña, material de verificación y hash de sesión. **No** se custodian tarjetas, CVV ni claves bancarias del comprador. El pago simulado recibe una referencia de pedido y consulta importe/moneda al backend; una aprobación escrita por el navegador no basta para marcarlo pagado.

Recorrido de la dirección: se captura en checkout, se valida cobertura en orders y se guarda un snapshot dentro del pedido. GraphQL la muestra únicamente a quien necesita consultar o cumplir ese pedido. Cambiar el perfil no reescribe la compra. Cancelar no borra historia. Los datos ficticios se conservan en volúmenes locales; eliminar una demostración completa requiere una acción manual explícita del operador. No existe endpoint de purga ni borrado automático; un entorno con datos reales necesita una política de conservación aprobada y un proceso de eliminación/anonimización antes de usarse.

### Inventario y operación de secretos

| Referencia simbólica | Emisor / consumidor | Finalidad y alcance | Ubicación |
| --- | --- | --- | --- |
| `VAULT_TOKEN` | Operador / vault-init y Vault dev | Provisionamiento inicial; nunca aplicaciones | Entorno del operador. El archivo `.env` existente está versionado: su retirada y revisión de credenciales queda pendiente del usuario; esta limpieza documental no lo modifica. |
| `identity-{servicio}` | Vault / un único servicio | Token lector de `secret/data/services/{servicio}`; 24 h, no renovable | Volumen privado, archivo token 0600, montaje aplicación `ro` |
| `{origen}.outgoing.{destino}` | bootstrap / origen y destino | `X-Gateway-Secret` exclusivo de esa conexión | KV de ambos componentes; lista completa en matriz de rutas |
| `gateway.outgoing.auth` | bootstrap / gateway y auth | También `X-Gateway-Auth-Secret` para operaciones Auth | KV de gateway/auth |
| `provider_hmac` | bootstrap / payments y simulator | Firma de avisos y comprobación temporal | Solo KV de esos dos servicios |

Responsable: operador del backend. Reiniciar Vault dev pierde secretos; volver a ejecutar vault-init y reiniciar las aplicaciones carga nuevas identidades. Reejecutar vault-init con Vault intacto **no rota** secretos de aristas existentes: los conserva. Para revocar una filtración, el operador debe detener los consumidores afectados, revocar sus tokens lectores en Vault, sustituir la arista en los KV de origen/destino y provisionar identidades lectoras; después reiniciar ambos y comprobar que la clave anterior recibe 403. El HMAC debe cambiarse coordinadamente en payments/simulator. Es un procedimiento manual, no una rotación automatizada implementada.

Las aplicaciones fallan al arrancar si Vault no responde y aún no tienen identidad cargada. Una vez cargada mantienen secretos en memoria: revocar solo el lector de Vault no revoca una arista ya cargada. No hay renovación automática. El aislamiento de red local y la identidad técnica no equivalen a TLS: HTTP se usa dentro de Docker y en localhost; un despliegue externo exige terminación HTTPS y una decisión explícita sobre cifrado interno y disco.

Los logs Python registran servicio, ID de correlación, método, **plantilla** de ruta, estado y duración. No registran cuerpo, query string, Bearer ni URL de checkout completa; los access logs de Uvicorn están desactivados en Compose. Los errores no devuelven SQL ni credenciales. Las pruebas verifican redacción, identidad falsificada, pago alterado, acceso ajeno y límites de consulta. No se afirma que exista un sistema central de auditoría.
