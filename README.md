# Fit Express · backend académico

Proyecto para la evaluación 2. El objetivo es mostrar las responsabilidades de cada servicio, las reglas de negocio y los controles pedidos en la rúbrica, con una implementación que se pueda explicar y ejecutar localmente.

El backend nuevo está en `services/` y se inicia con `docker-compose.yml`. El backend anterior y su base se conservan; el frontend todavía no está conectado a esta implementación.

## Cómo está organizado

- **auth:** login, introspección y logout; guarda las sesiones en su propio SQLite.
- **clients:** registro, cuentas, hashes, roles y perfiles. Auth consulta sus APIs privadas de cuenta.
- **inventory:** productos, combos, disponibilidad y reservas de stock.
- **orders:** checkout, estados, despacho, ventas y comprobantes.
- **payments:** pagos simulados y reembolsos.
- **GraphQL:** Node/Express/Apollo, como el ejemplo del profesor; seis consultas que reúnen las APIs privadas.
- **API Gateway:** entrada pública, rutas permitidas y validación de sesión/rol.
- **Vault:** credenciales privadas de integración, cargadas al arrancar.
- **Simulador:** proveedor de pago de prueba, separado de payments.

Cada servicio de negocio usa su propio SQLite y llama a los demás mediante HTTP privado. Los correos y pagos son simulados.

## Arrancar y detener

Requiere Docker/Compose. El usuario debe tener `VAULT_TOKEN` definido en su entorno o configuración existente; no hay token por defecto ni se modifican archivos `.env`.

```sh
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

Solo se publica el gateway en `127.0.0.1:8000`. Documentación: [localhost:8000/docs](http://localhost:8000/docs). Se puede elegir otro puerto mediante `FITEXPRESS_PORT` al ejecutar Compose.

```sh
docker compose stop
```

Los datos se conservan en volúmenes. Vault funciona en modo dev y pierde secretos al reiniciarse. Sus tokens de lectura duran 24 horas; las aplicaciones cargan las credenciales una sola vez. Para volver a provisionarlas y cargarlas:

```sh
docker compose run --rm vault-init
docker compose restart auth clients inventory orders payments graphql simulator gateway
```

## Cuentas y demostración

Crear un administrador, ingresando la contraseña cuando se solicite:

```sh
docker compose exec clients python -m services.manage create-admin --identificador admin@fitexpress.test
```

Para la demostración, `seed-demo` crea/actualiza cinco cuentas ficticias: `administrador`, `cajero`, `despacho`, `dueno` y `cliente`, bajo `@fitexpress.test`. Pide una contraseña de al menos 12 caracteres para esas cuentas; no la imprime. Luego se usa la misma contraseña en `smoke`:

```sh
docker compose exec clients python -m services.manage seed-demo
docker compose exec -it gateway python -m services.smoke --url http://127.0.0.1:8000
```

La demostración asigna un cajero a la caja Web y realiza catálogo → checkout → pago aprobado → comprobante → preparación → envío → entrega. Crea un pedido y consume stock de prueba.

Los mensajes de correo simulado se consultan localmente con `python -m services.manage mensajes` dentro del contenedor clients. Contienen códigos de verificación; no hay una ruta pública para leerlos.

## Reglas técnicas esenciales

- Login recibe `{username, password}` y devuelve `{access_token, token_type: "bearer", expires_in: 28800}`. El cliente usa `Authorization: Bearer <access_token>`. Logout revoca esa sesión.
- El gateway consulta `/introspect` en Auth, y transmite usuario/rol en `X-Authenticated-*`, junto con el secreto técnico `X-Gateway-Secret`. Las cabeceras del navegador se descartan; los servicios verifican llamador, roles y propiedad. La sesión personal no se propaga a los servicios.
- Auth compara la versión actual de la cuenta en clients: cambiar contraseña/rol, desactivar o perder la verificación invalida sesiones. Los hashes nunca salen por APIs públicas.
- Las acciones de negocio usan `Idempotency-Key`: repetir la misma clave recupera la operación; otro contenido produce 409. Evita repetir venta, stock o devolución.
- El carrito no reserva. Checkout crea una reserva completa de 15 minutos, con precios y tarifa oficiales. Una tarea periódica vence los pedidos pendientes.
- El aviso de pago se verifica y aplica durante la solicitud. Si falla una dependencia, se reenvía el mismo resultado del simulador. Cancelaciones y decisiones interrumpidas se repiten con la misma clave. No hay workers de recuperación automática.
- GraphQL conserva permisos por campo, paginación, profundidad máxima 6, costo máximo 2000, ejecución máxima de 10 s y errores parciales. Agrupa lecturas por página/pedido, sin caché de tareas ni optimización por selección de campos.
- Gateway usa contadores en memoria por minuto fijo: 60 solicitudes por usuario, 120 por IP anónima y cinco fallos de login por IP. Es una demostración local de una instancia.
- Las credenciales de integración quedan en Vault y volúmenes privados; se cargan al arrancar. Su cambio es manual y requiere reiniciar servicios.

No se añade infraestructura de producción ni renovación automática de secretos. Se conservan los controles necesarios para demostrar la seguridad y las reglas del proyecto.

## Pruebas

```sh
npm ci --prefix services/graphql
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r services/requirements-dev.txt
.venv/bin/python -m pytest -c services/pytest.ini services/tests
.venv/bin/ruff check services
npm run check --prefix services/graphql
```

Las pruebas requieren Node y ejecutan el servidor Apollo real contra las APIs Python, con bases temporales y credenciales de prueba. Incluyen el recorrido por sockets HTTP y el vencimiento automático. La suite histórica `backend_api/tests` corresponde al backend anterior y se ejecuta por separado.

Resultado actual: **34 pruebas aprobadas** y demostración con Docker/Vault real comprobada. [Estado y evidencias](docs/estado-backend-e2.md). [Reglas](docs/reglas-pedidos.md), [contratos REST](docs/contratos-rest.md), [GraphQL](docs/contratos-graphql.md) y [plan HTML](docs/plan-evaluacion-2.html).

## Organización y referencia del curso

Cada aplicación tiene su carpeta: `services/auth/auth_service.py`, `services/gateway/gateway.py`, `services/<modulo>/backend_api.py` y `services/graphql/server.js`. Los DTO, helpers de SQLite/HTTP y la idempotencia de las operaciones se comparten para conservar las reglas existentes; las fábricas `create_app` permiten las pruebas con bases temporales. El Dockerfile Python es común; GraphQL tiene su propio Dockerfile y lockfile npm.

Referencia: [Unidad 2 del profesor](https://github.com/evivanco/dwm20260203/tree/b239e1b9a1d9d0c3fa2673ae36d3a1ceded08a8e/Unidad%202). Se replica Auth `/login`–`/introspect`–`/logout`, Bearer, cabeceras verificadas y Apollo/Express. Se usa Express 4.21.2, compatible con Apollo 3.13.0, en lugar de forzar la combinación con Express 5 declarada en el ejemplo. Se conserva SQLite, elección autorizada por el docente, y la agregación privada requerida por la evaluación.

`backend_api/` y `api_gateway/` contienen la implementación anterior con cambios locales del usuario; no se utilizan en el Compose oficial. El frontend aún espera el contrato anterior y requiere una migración posterior. Las sesiones de la implementación previa deben iniciarse de nuevo; no se borra la base histórica ni se migran sus sesiones automáticamente.
