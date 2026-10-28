# Estado del backend · 28 de octubre de 2026

Rama `feat/backend-evaluacion-2`, base `2157235`, versionada en diez commits por responsabilidad. El despliegue oficial es `docker-compose.yml`. Las carpetas antiguas `backend_api/` y `api_gateway/`, su base y sus cambios locales se conservan como referencia; no forman parte del arranque oficial. El frontend sigue pendiente de migración.

## Alineación con el profesor

Referencia revisada: [Unidad 2, commit b239e1b](https://github.com/evivanco/dwm20260203/tree/b239e1b9a1d9d0c3fa2673ae36d3a1ceded08a8e/Unidad%202).

| Parte | Implementación actual |
| --- | --- |
| Auth Service | `services/auth/auth_service.py`: `/login`, `/introspect`, `/logout`. Sesiones en su propio SQLite; credenciales/cuentas consultadas por API privada a clients. |
| API Gateway | `services/gateway/gateway.py`: HTTPBearer, consulta Auth e inyecta `X-Authenticated-*` y `X-Gateway-Secret`. Descarta identidad declarada por el navegador. |
| Servicios | Carpetas clients, inventory, orders, payments y simulator, cada una con `backend_api.py` y `schema.sql`. Helpers comunes de SQLite/HTTP e idempotencia; `create_app` para aislar pruebas. |
| GraphQL | Node/Express/Apollo, con `server.js`, `resolvers.js`, `schema.graphql` y lockfile npm. Conserva seis consultas, APIs privadas, batching y permisos; no consulta bases ajenas. |
| Persistencia | SQLite autorizado por el docente. Se conservan datos y reglas de Fit Express, en lugar de las respuestas fijas del ejemplo de gateway. |
| Despliegue | Un Compose oficial, imagen Python compartida y una imagen Node de GraphQL. Solo el gateway publica un puerto en localhost. |

Apollo 3.13.0 reproduce la API del ejemplo. Se fijó Express 4.21.2 para satisfacer su dependencia compatible, en lugar de forzar Express 5. No se copian los errores del ejemplo ni se exponen contraseñas por GraphQL. Vault mantiene identidades limitadas por servicio, cargadas al arrancar.

Los contratos suman **61 propios**: Auth 3, clients 12, inventory 13, orders 20, payments 12 y GraphQL 1. I01 pasa a `/introspect` de Auth; I19 es la consulta privada de credenciales en clients. Se mantienen seis contratos del simulador, 34 rutas públicas propias y dos entradas de demostración.

## Alcance educativo

Pagos y correo simulados. El aviso de pago se verifica y aplica en la solicitud. Los reintentos son explícitos y conservan referencia/idempotencia; solo el vencimiento de reservas usa una tarea periódica. No hay caché de tareas ni recuperación automática de pagos. La lógica de pedidos, snapshots, stock, caja, comprobantes y excepciones administrativas se conserva.

Login recibe `{username,password}` y devuelve `{access_token,token_type,expires_in}`. La sesión dura ocho horas. Auth compara la versión actual de la cuenta para invalidarla tras cambios de credenciales/rol/desactivación. El contexto interno transporta un rol dentro de `X-Authenticated-Roles`; las cuentas del proyecto siguen teniendo un rol único.

## Verificación ejecutada

- **34 pruebas aprobadas**, cero fallos: [JUnit](evidencias/backend-e2/pytest.xml) y [resumen](evidencias/backend-e2/resultado.json).
- Las pruebas ejecutan Apollo en un proceso Node real contra las APIs Python. Incluyen recorrido por sockets HTTP, reserva/vencimiento, permisos, errores parciales, pagos duplicados, cancelaciones y reembolsos.
- Prueba nueva: un cliente que falsifica `X-Authenticated-*` sigue siendo Cliente; Auth privado rechaza una llamada sin identidad técnica.
- Ruff, formato Python, comprobación de sintaxis JavaScript y configuración Compose aprobados.
- Imágenes Python y Node compiladas; **nueve servicios saludables con Vault real**: [evidencia](evidencias/backend-e2/docker-vault.json).
- Pedido **4 entregado**, pago aprobado y comprobante `FE-00000004`. Se conservan el pedido, comprobante y la misma sesión Bearer tras reiniciar las ocho aplicaciones; logout invalida el token con 401 posterior.
- Ocho identidades leen su propio secreto (200), y 56 lecturas cruzadas reciben 403. Siete componentes privados rechazan acceso directo sin identidad. Solo el gateway publica `127.0.0.1:8000`; volúmenes de identidad en solo lectura y sin token raíz en aplicaciones.

No se ejecutó la suite histórica ni se modificó el frontend, `.env` o configuración Docker del usuario. Las sesiones antiguas de clients requieren iniciar sesión de nuevo; sus tablas históricas no se borran ni se migran automáticamente a Auth.

## Pendientes de la entrega

Integración del frontend con el nuevo contrato Bearer y GraphQL, UML de servicios/gateway, matrices formales, política de datos y ADR/medición de aplicabilidad de analítica/gRPC. El diagrama de dominio del 24 de octubre permanece como referencia y debe actualizar la separación Auth/clients en el UML final. No se añaden objetivos de infraestructura de producción.
