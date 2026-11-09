# Contratos REST

Catálogo del backend implementado en `services/`. El prefijo público es `/api`; las rutas privadas requieren identidad técnica. El frontend de entrega es una demo estática y no consume estos contratos. Los ejemplos son ilustrativos.

## Convenciones comunes

| Aspecto | Contrato |
| --- | --- |
| Ruta externa | API Gateway agrega /api a las rutas S autorizadas. S03/S13–S16/S21/S22/S30 y todas las I son privadas. S06 ahora se dirige a orders. |
| Sesión | Authorization: Bearer con token personal del consumidor, ocho horas fijas; no cookies. Se obtiene en S01 y revoca en S02. Nunca un token compartido de integración desde el frontend. |
| Servicio privado | X-Gateway-Secret con credencial del consumidor obtenida de Vault y verificada por el destino; identidad/alcance por consumidor, no solo una cabecera de rol. API Gateway elimina cabeceras técnicas del navegador antes de inyectar las propias. Auth requiere además X-Gateway-Auth-Secret para login/introspect/logout. |
| Contexto | El gateway valida el Bearer mediante Auth /introspect y genera X-Authenticated-User-ID/User/Roles/Client-ID/Email-Verified. Solo se aceptan tras verificar al llamador técnico; nunca se copian del navegador. Operaciones derivadas de una decisión persistida conservan su actor y referencia; los reintentos técnicos no necesitan una nueva aprobación. |
| Cuerpo y correlación | JSON, Content-Type application/json, máximo inicial 64 KiB; X-Request-ID válido o generado por gateway, propagado sin secretos. Documentos S27/S32 devuelven HTML. |
| Idempotencia | Idempotency-Key opaca de 1–128 caracteres en creaciones/acciones de negocio repetibles; no login/logout ni lecturas, aunque I01/I04/I16 usen POST. Misma clave/actor/operación/contenido recupera resultado; diferente contenido devuelve 409. |
| IDs y dinero | IDs positivos, referencias opacas del proveedor como texto. Importes enteros CLP; entradas no negativas y totales compatibles con Int GraphQL. Acumulados de reporte como cadena decimal con signo cuando corresponde. |
| Listas | pagina desde 1, limite por defecto 12 catálogo/20 otros, máximo 50; items+paginacion. Referencias pequeñas preconfiguradas S06/S13 y caja única S28 conservan arrays completos acotados por seeds. |
| Fechas | Desde/hasta YYYY-MM-DD en America/Santiago; incluir ambos días usando fin exclusivo del siguiente. Salida ISO 8601 UTC. Queryparams inválidos producen 422. |
| Errores | JSON {detail: mensaje controlado, codigo: código de aplicación, request_id: referencia}; validación puede incluir campos sin repetir valores sensibles. 401 sesión, 403 rol/servicio, 404 recurso inexistente/ajeno, 409 estado/stock/versión/idempotencia, 422 entrada, 429 frecuencia con Retry-After, 502/503 dependencia controlada. |
| Frecuencia | 60/min/usuario, 120/min/IP anónima; cinco fallos de login/min/IP bloquean nuevos intentos temporalmente. No contar otra vez llamadas privadas derivadas. Contadores por minuto fijo en memoria para una instancia académica. |

**Alcance académico simplificado:** las acciones se resuelven en la solicitud; solo el vencimiento de reservas usa una tarea periódica. No hay workers de recuperación de pagos ni cancelaciones. Ante un fallo, el operador/cliente repite la misma clave o el aviso del simulador. Vault se carga al arrancar.

Ante una respuesta perdida, el consumidor repite la misma clave de idempotencia. Las pruebas comprueban que no se repiten efectos sobre stock, venta, comprobante o devolución.

## Matriz de rutas y destinos

| ID | Método/ruta | Destino | Exposición |
| --- | --- | --- | --- |
| S01 | `POST /login` | auth | API Gateway con permiso específico |
| S02 | `POST /logout` | auth | API Gateway con permiso específico |
| S03 | `GET /perfil` | clients | Privada |
| S04 | `POST /registro` | clients | API Gateway con permiso específico |
| S05 | `POST /clientes/verificar-correo` | clients | API Gateway con permiso específico |
| S07 | `GET /admin/clientes` | clients | API Gateway con permiso específico |
| S08 | `POST /admin/clientes` | clients | API Gateway con permiso específico |
| S09 | `PATCH /admin/clientes/{id}` | clients | API Gateway con permiso específico |
| S10 | `GET /admin/usuarios` | clients | API Gateway con permiso específico |
| S11 | `POST /admin/usuarios` | clients | API Gateway con permiso específico |
| S12 | `PATCH /admin/usuarios/{id}` | clients | API Gateway con permiso específico |
| S13 | `GET /categorias` | inventory | Privada |
| S14 | `GET /productos` | inventory | Privada |
| S15 | `GET /productos/{id}` | inventory | Privada |
| S16 | `GET /combos` | inventory | Privada |
| S17 | `POST /productos` | inventory | API Gateway con permiso específico |
| S18 | `PUT /productos/{id}` | inventory | API Gateway con permiso específico |
| S19 | `DELETE /productos/{id}` | inventory | API Gateway con permiso específico |
| S06 | `GET /comunas` | orders | API Gateway con permiso específico |
| S20 | `POST /ordenes` | orders | API Gateway con permiso específico |
| S21 | `GET /ordenes` | orders | Privada |
| S22 | `GET /ordenes/{id}` | orders | Privada |
| S23 | `POST /ordenes/{id}/cancelaciones` | orders | API Gateway con permiso específico |
| S24 | `POST /ordenes/{id}/preparacion` | orders | API Gateway con permiso específico |
| S25 | `POST /ordenes/{id}/envios` | orders | API Gateway con permiso específico |
| S26 | `POST /ordenes/{id}/entregas` | orders | API Gateway con permiso específico |
| S27 | `GET /ordenes/{id}/orden-despacho` | orders | API Gateway con permiso específico |
| S28 | `GET /cajas` | orders | API Gateway con permiso específico |
| S29 | `PATCH /cajas/{id}` | orders | API Gateway con permiso específico |
| S30 | `GET /reportes/ventas` | orders | Privada |
| S31 | `POST /ventas/{id}/comprobantes` | orders | API Gateway con permiso específico |
| S32 | `GET /ventas/{id}/comprobante` | orders | API Gateway con permiso específico |
| S33 | `POST /ventas/{id}/comprobante/envios` | orders | API Gateway con permiso específico |
| S34 | `POST /pagos` | payments | API Gateway con permiso específico |
| S35 | `GET /pagos/{id}` | payments | API Gateway con permiso específico |
| S36 | `POST /webhooks/pagos/{proveedor}` | payments | API Gateway con permiso específico |
| S37 | `POST /solicitudes-reembolso` | payments | API Gateway con permiso específico |
| S38 | `GET /solicitudes-reembolso` | payments | API Gateway con permiso específico |
| S39 | `GET /solicitudes-reembolso/{id}` | payments | API Gateway con permiso específico |
| S40 | `POST /solicitudes-reembolso/{id}/decisiones` | payments | API Gateway con permiso específico |
| S42 | `POST /reembolsos/{id}/reintentos` | payments | API Gateway con permiso específico |
| S41 | `POST /graphql` | graphql | API Gateway con permiso específico |
| I01 | `POST /introspect` | auth | Privada |
| I19 | `POST /interno/auth/credenciales` | clients | Privada; solo Auth |
| I02 | `GET /interno/clientes/{id}` | clients | Privada |
| I03 | `GET /interno/usuarios/{id}` | clients | Privada |
| I04 | `POST /interno/catalogo/consultas` | inventory | Privada |
| I05 | `POST /interno/reservas` | inventory | Privada |
| I06 | `GET /interno/reservas/{id}` | inventory | Privada |
| I07 | `POST /interno/reservas/{id}/consumos` | inventory | Privada |
| I08 | `POST /interno/reservas/{id}/liberaciones` | inventory | Privada |
| I09 | `POST /interno/reservas/{id}/restituciones` | inventory | Privada |
| I10 | `GET /interno/ordenes/{id}/cobro` | orders | Privada |
| I11 | `POST /interno/ordenes/{id}/resultados-pago` | orders | Privada |
| I12 | `POST /interno/ordenes/{id}/vencimientos` | orders | Privada |
| I13 | `POST /interno/ordenes/{id}/resultados-reembolso` | orders | Privada |
| I18 | `POST /interno/ordenes/{id}/autorizaciones-reembolso` | orders | Privada |
| I14 | `POST /interno/reembolsos` | payments | Privada |
| I15 | `GET /interno/pagos/{id}/estado` | payments | Privada |
| I16 | `POST /interno/pagos/consultas` | payments | Privada |
| I17 | `GET /interno/reportes/movimientos` | payments | Privada |

## Entradas y permisos

Los campos, tipos y validaciones están en [DTO](../services/dto.py). La [matriz de permisos](informe-evaluacion-2.md#matriz-de-rutas-y-permisos) indica roles y condiciones por operación. El código de cada servicio es la referencia para respuestas y reglas de negocio.

## Ejemplos

### Inicio de sesión

`POST /api/login`, sin Bearer:

```json
{"username":"cliente@example.com","password":"clave-de-ejemplo"}
```

Respuesta nominal (el token mostrado es un marcador):

```json
{"access_token":"<token-personal>","token_type":"bearer","expires_in":28800}
```

### Crear pedido

`POST /api/ordenes`, `Authorization: Bearer <token-personal>` e `Idempotency-Key: compra-ejemplo-1`:

```json
{"direccion":{"calle":"Providencia","numero":"1234","comuna_id":1},"items":[{"producto_id":1,"cantidad":1}]}
```

Devuelve el pedido pendiente con identificador, total calculado y reserva. Un faltante de stock o conflicto de idempotencia devuelve 409. El consumidor no fija cliente, precio ni estado.

### Iniciar pago

`POST /api/pagos`, Bearer e idempotencia:

```json
{"orden_id":1}
```

Devuelve el intento y una URL del proveedor simulado. Un resultado del navegador no confirma por sí solo el pago: payments verifica firma, resultado, importe y moneda con el simulador.

### Cancelación

`POST /api/ordenes/1/cancelaciones`, Bearer e idempotencia:

```json
{"motivo":"No podré recibir el pedido"}
```

Cliente propietario o Administrador pueden cancelar antes de preparar. La cancelación pagada restituye stock y solicita devolución; la pendiente libera la reserva.

### Error de sesión

Sin Bearer en una ruta protegida: HTTP 401. El cuerpo incluye `detail`, `codigo` y `request_id`; una denegación por rol devuelve 403. No se devuelven credenciales ni SQL.

## Proveedor simulado

Sus seis operaciones están implementadas en [simulator/backend_api.py](../services/simulator/backend_api.py). El gateway publica solo la apertura del checkout por token y el envío de su resultado. Las llamadas internas de creación, consulta y devolución exigen identidad técnica.

Los recorridos ejecutables se encuentran en [test_backend.py](../services/tests/test_backend.py), [test_tcp.py](../services/tests/test_tcp.py) y [smoke.py](../services/smoke.py).
