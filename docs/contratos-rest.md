# Contratos REST e integraciones de Fit Express

Diseño del 24 de octubre de 2026. Completa el [catálogo](reglas-pedidos.md#catálogo-de-endpoints) y las decisiones de la ronda de preguntas. Todos los ejemplos son ficticios e independientes; reutilizan IDs para distintos escenarios y no forman una ejecución secuencial. Se cubren S01–S42 e I01–I19: 61 contratos propios, más seis del simulador. **Implementación del 28 de octubre, alineada con el profesor:** rutas presentes en `services/`; ejemplos de este documento siguen siendo ficticios. Los resultados ejecutados, alcance y limitaciones están en [estado-backend-e2.md](estado-backend-e2.md).

## Convenciones comunes

| Aspecto | Contrato objetivo |
| --- | --- |
| Ruta externa | API Gateway agrega /api a las rutas S autorizadas. S03/S13–S16/S21/S22/S30 y todas las I son privadas. S06 ahora se dirige a orders. |
| Sesión | Authorization: Bearer con token personal de sessionStorage, ocho horas fijas; no cookies. Se obtiene en S01 y revoca en S02. Nunca un token compartido de integración desde el frontend. |
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

Los métodos y ejemplos de salida son nominales. Una acción que recibió trabajo y quedó en conciliación persistida puede devolver 202 con {operacion_id, estado: procesando} y Retry-After; ese estado es del workflow, no del pedido. El cliente repite con la misma clave para recuperar el resultado, nunca crea otra operación a ciegas. No mantener transacciones SQL bloqueadas durante llamadas de red. Conservar deduplicación financiera por evento/transacción/reembolso y unicidad de venta/comprobante aunque se pierda una respuesta.

## Campos y validaciones compartidas

| DTO de entrada | Campos y reglas |
| --- | --- |
| Login | username:string requerido, password:string requerido; errores genéricos. |
| ClienteRegistro | nombres, apellidos, rut, direccion, provincia, region, sexo, telefono:string requeridos no vacíos; comuna_id:ID; fecha_nacimiento:fecha válida; email:correo válido. RUT normalizado y dígito verificador, email/identificador únicos. Conservar formulario actual; no añadir restricciones de edad no definidas. |
| ClientePatch | Campos del registro opcionales y activo:boolean opcional; validar los presentes. Sin edición de roles o hashes por aquí. |
| Verificación | cliente_id:ID, codigo:string de seis dígitos, password:string mínimo ocho. Código único por cuenta, vence en 15 min y máximo cinco fallos, según lógica actual. Regeneración por administración existente; email real pospuesto. |
| Funcionario | identificador:string, password:string mínimo ocho y rol:administrador/cajero/despacho/dueno; PATCH hace opcionales esos campos y activo:boolean. |
| ProductoIn | nombre:string no vacío, descripcion:string/null, precio:int >=0, precio_oferta:int/null menor que precio, stock:int >=0 y no inferior a reservas, categoria_id:ID válido. PUT requiere todos los campos editables. |
| Checkout | direccion:{calle,numero:string requeridos; departamento:string/null; comuna_id:ID habilitado}; items:listado no vacío de {producto_id XOR combo_id, cantidad:int >=1}. Tope técnico inicial 50 líneas; no truncar legacy ni aceptar precios/cliente/estado impuestos. |
| Acción de pedido | version:int opcional como precondición; servidor siempre comprueba estado/versión. Cancelación exige motivo:string recortado de 1–1000 caracteres. |
| Solicitud/decisión | pedido_id y motivo textual de 1–1000 caracteres; sin adjuntos. Decisión aprobar/rechazar + motivo textual obligatorio. El servicio obtiene actor/importe de fuentes verificadas. |
| Paginación/filtros | Texto de búsqueda recortado, máximo 100 caracteres; estado de enum definido; fechas válidas y desde<=hasta. Campos privilegiados no se ignoran para evitar el control. |

RUT, contacto, dirección, nacimiento/sexo, pedidos y finanzas son datos restringidos; sesiones, claves, códigos y credenciales son secretos o material de autenticación. Respuestas se proyectan por finalidad, no se copia toda la fila. Auth revalida cuenta/rol y revoca sesiones por cambio de clave/rol/desactivación. PBKDF2 con sal ya existe; su parametrización y evidencia de seguridad se revisarán en M7, sin afirmar que esta documentación prueba su suficiencia.

## Matriz de rutas y destinos

| ID | Método/ruta | Destino | Exposición objetivo |
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

## Fichas de operación

Cada solicitud incluye las cabeceras de su clase y la ruta de la ficha. path/query/body se muestran en el ejemplo; los nombres de parámetros de ruta se sustituyen por IDs ficticios positivos. El campo respuesta describe cuerpo y status nominales.

### S01 · POST /login

- **Destino y acceso:** auth; Sin sesión previa; credenciales válidas.
- **Regla:** Credenciales genéricas ante error; Cliente requiere correo verificado. Sesión opaca hasheada en servidor. Cinco fallos/min/IP activan bloqueo temporal. Nunca registrar ni devolver hashes.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "username": "cliente@example.com",
      "password": "<clave-de-prueba>"
    },
    "headers": {
      "Content-Type": "application/json"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "access_token": "<token-personal>",
      "token_type": "bearer",
      "expires_in": 28800
    }
  }
}
```

### S02 · POST /logout

- **Destino y acceso:** auth; Usuario con sesión válida.
- **Regla:** El gateway obtiene el Bearer y llama a Auth con {token}; revoca solo la sesión presentada. El cliente limpia sessionStorage. Si ya expiró, el frontend la limpia igualmente ante 401. No usa Idempotency-Key.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": null,
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "message": "Sesión finalizada"
    }
  }
}
```

### S03 · GET /perfil

- **Destino y acceso:** clients; GraphQL con identidad de servicio y sesión válida del usuario; solo sus propios datos.
- **Regla:** Privado; reemplazo de /yo. No acepta usuario_id arbitrario. Funcionarios sin cliente devuelven cliente_id/perfil nulos; los campos no se leen de tablas ajenas.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 10,
      "identificador": "cliente@example.com",
      "rol": "cliente",
      "cliente_id": 7,
      "email_verificado": true,
      "perfil": {
        "nombres": "Cliente",
        "apellidos": "Demo",
        "rut": "11111111-1",
        "email": "cliente@example.com",
        "telefono": "+56900000000",
        "direccion": "Calle Demo 100",
        "comuna": "Comuna Demo"
      }
    }
  }
}
```

### S04 · POST /registro

- **Destino y acceso:** clients; Visitante; validación y límite de solicitudes.
- **Regla:** ClienteRegistro; crear cuenta pendiente/código de seis dígitos por 15 min y solicitar mensaje simulado. No retornar código ni hash. Registro admin también verifica correo; sin sesión de Cliente hasta definir clave/verificar.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "nombres": "Cliente",
      "apellidos": "Demo",
      "rut": "11111111-1",
      "direccion": "Calle Demo 100",
      "comuna_id": 1,
      "provincia": "Provincia Demo",
      "region": "Región Demo",
      "fecha_nacimiento": "2000-01-01",
      "sexo": "otro",
      "email": "cliente@example.com",
      "telefono": "+56900000000"
    },
    "headers": {
      "Content-Type": "application/json",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "cliente_id": 7,
      "estado": "pendiente"
    }
  }
}
```

### S05 · POST /clientes/verificar-correo

- **Destino y acceso:** clients; Titular con código de verificación válido.
- **Regla:** Código de seis dígitos vigente, máximo cinco fallos por código, se invalida al usarse. El ejemplo usa un marcador: sustituirlo por un código ficticio válido en la prueba. Conservar la definición de contraseña de la implementación actual.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "cliente_id": 7,
      "codigo": "<codigo-de-6-digitos>",
      "password": "<clave-de-prueba>"
    },
    "headers": {
      "Content-Type": "application/json",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "verificado": true
    }
  }
}
```

### S07 · GET /admin/clientes

- **Destino y acceso:** clients; Administrador.
- **Regla:** Administrador; datos de Cliente para mantenimiento. Sin códigos, hashes o sesiones. No exponerlos por query perfil/pedido de otro actor.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "pagina": 1,
      "limite": 20
    },
    "headers": {
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 7,
          "nombres": "Cliente",
          "apellidos": "Demo",
          "rut": "11111111-1",
          "direccion": "Calle Demo 100",
          "comuna_id": 1,
          "provincia": "Provincia Demo",
          "region": "Región Demo",
          "fecha_nacimiento": "2000-01-01",
          "sexo": "otro",
          "email": "cliente@example.com",
          "telefono": "+56900000000",
          "email_verificado_at": "2026-10-24T14:00:00Z",
          "activo": true
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

### S08 · POST /admin/clientes

- **Destino y acceso:** clients; Administrador.
- **Regla:** ClienteRegistro; crear cuenta pendiente/código de seis dígitos por 15 min y solicitar mensaje simulado. No retornar código ni hash. Registro admin también verifica correo; sin sesión de Cliente hasta definir clave/verificar.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "nombres": "Cliente",
      "apellidos": "Demo",
      "rut": "11111111-1",
      "direccion": "Calle Demo 100",
      "comuna_id": 1,
      "provincia": "Provincia Demo",
      "region": "Región Demo",
      "fecha_nacimiento": "2000-01-01",
      "sexo": "otro",
      "email": "cliente@example.com",
      "telefono": "+56900000000"
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "cliente_id": 7,
      "estado": "pendiente"
    }
  }
}
```

### S09 · PATCH /admin/clientes/{id}

- **Destino y acceso:** clients; Administrador.
- **Regla:** PATCH de ClienteRegistro y activo, todos opcionales; al menos un cambio. Cambio de email exige verificar otra vez y revoca sesiones; desactivar/clave/rol invalidan sesiones afectadas. Reusar la regeneración de código del administrador ya existente para cuentas pendientes.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "telefono": "+56900000001",
      "activo": true
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 7
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 7,
      "nombres": "Cliente",
      "apellidos": "Demo",
      "rut": "11111111-1",
      "direccion": "Calle Demo 100",
      "comuna_id": 1,
      "provincia": "Provincia Demo",
      "region": "Región Demo",
      "fecha_nacimiento": "2000-01-01",
      "sexo": "otro",
      "email": "cliente@example.com",
      "telefono": "+56900000000",
      "email_verificado_at": "2026-10-24T14:00:00Z",
      "activo": true
    }
  }
}
```

### S10 · GET /admin/usuarios

- **Destino y acceso:** clients; Administrador.
- **Regla:** Solo funcionarios; roles administrador/cajero/despacho/dueno. Sin password_hash o tokens.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "pagina": 1,
      "limite": 20
    },
    "headers": {
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 20,
          "identificador": "cajero.demo",
          "rol": "cajero",
          "activo": true
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

### S11 · POST /admin/usuarios

- **Destino y acceso:** clients; Administrador.
- **Regla:** Identificador único, rol permitido y clave mínima de ocho caracteres; no crear un Cliente por esta ruta.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "identificador": "cajero.demo",
      "rol": "cajero",
      "password": "<clave-de-prueba>"
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 20,
      "identificador": "cajero.demo",
      "rol": "cajero",
      "activo": true
    }
  }
}
```

### S12 · PATCH /admin/usuarios/{id}

- **Destino y acceso:** clients; Administrador.
- **Regla:** PATCH de identificador/rol/password/activo, al menos un cambio; roles vigentes al autorizar, invalidar sesiones por clave/rol/desactivación y evitar quedar sin administrador operativo.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "rol": "cajero",
      "activo": true
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 20
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 20,
      "identificador": "cajero.demo",
      "rol": "cajero",
      "activo": true
    }
  }
}
```

### S13 · GET /categorias

- **Destino y acceso:** inventory; GraphQL autorizado técnicamente; contexto anónimo permitido para campos públicos.
- **Regla:** Referencia preconfigurada; sin mantenedor. Privado al migrar G03.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": [
      {
        "id": 1,
        "nombre": "Bowls"
      }
    ]
  }
}
```

### S14 · GET /productos

- **Destino y acceso:** inventory; GraphQL autorizado técnicamente; anónimo para catálogo público, ofertas según identidad verificada.
- **Regla:** Filtro opcional producto_id/categoria_id/busqueda/solo_disponibles/incluir_inactivos. Inactivos y stock solo Administrador/Dueño. Oferta y precio_final dependen del usuario verificado; disponibilidad incluye reservas. Nombre+ID ascendentes.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "categoria_id": 1,
      "busqueda": "Bowl",
      "solo_disponibles": false,
      "pagina": 1,
      "limite": 12
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 1,
          "nombre": "Bowl Proteico Demo",
          "descripcion": "Pollo, quinoa y verduras.",
          "precio": 6500,
          "precio_oferta": null,
          "precio_final": 6500,
          "disponible": true,
          "activo": true,
          "categoria_id": 1,
          "categoria": "Bowls"
        }
      ],
      "paginacion": {
        "pagina": 1,
        "limite": 12,
        "total": 1
      }
    }
  }
}
```

### S15 · GET /productos/{id}

- **Destino y acceso:** inventory; GraphQL autorizado técnicamente; anónimo para datos públicos, ofertas según identidad verificada.
- **Regla:** Producto vigente; inactivo devuelve 404 salvo consulta administrativa autorizada. Campos de stock/oferta según rol; no usarlo para reconstruir el nombre histórico de una compra.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    },
    "path": {
      "id": 1
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 1,
      "nombre": "Bowl Proteico Demo",
      "descripcion": "Pollo, quinoa y verduras.",
      "precio": 6500,
      "precio_oferta": null,
      "precio_final": 6500,
      "disponible": true,
      "activo": true,
      "categoria_id": 1,
      "categoria": "Bowls"
    }
  }
}
```

### S16 · GET /combos

- **Destino y acceso:** inventory; GraphQL autorizado técnicamente; anónimo para catálogo público, ofertas según identidad verificada.
- **Regla:** Filtros combo_id/busqueda/solo_disponibles; precio/disponibilidad de inventory. Componentes inactivos o sin unidades libres hacen no disponible el combo. Sin POST/PUT/DELETE de combos.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "pagina": 1,
      "limite": 12
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 1,
          "nombre": "Combo Demo",
          "descripcion": null,
          "precio": 9000,
          "precio_oferta": null,
          "precio_final": 9000,
          "disponible": true,
          "productos": [
            {
              "id": 1,
              "nombre": "Bowl Proteico Demo",
              "cantidad": 1
            }
          ]
        }
      ],
      "paginacion": {
        "pagina": 1,
        "limite": 12,
        "total": 1
      }
    }
  }
}
```

### S17 · POST /productos

- **Destino y acceso:** inventory; Administrador o Dueño.
- **Regla:** ProductoIn; PUT reemplaza campos editables completos y mantiene estado activo actual. Validar categoría, precio/oferta, stock no inferior a reservas y rango de importes. Crear no inventa componentes/combos; editar no cambia snapshots de pedidos.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "nombre": "Bowl Proteico Demo",
      "descripcion": "Pollo, quinoa y verduras.",
      "precio": 6500,
      "precio_oferta": null,
      "categoria_id": 1,
      "stock": 10
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 1,
      "nombre": "Bowl Proteico Demo",
      "descripcion": "Pollo, quinoa y verduras.",
      "precio": 6500,
      "precio_oferta": null,
      "precio_final": 6500,
      "disponible": true,
      "activo": true,
      "categoria_id": 1,
      "categoria": "Bowls",
      "stock": 10
    }
  }
}
```

### S18 · PUT /productos/{id}

- **Destino y acceso:** inventory; Administrador o Dueño.
- **Regla:** ProductoIn; PUT reemplaza campos editables completos y mantiene estado activo actual. Validar categoría, precio/oferta, stock no inferior a reservas y rango de importes. Crear no inventa componentes/combos; editar no cambia snapshots de pedidos.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "nombre": "Bowl Proteico Demo",
      "descripcion": "Pollo, quinoa y verduras.",
      "precio": 6500,
      "precio_oferta": null,
      "categoria_id": 1,
      "stock": 10
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 1
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 1,
      "nombre": "Bowl Proteico Demo",
      "descripcion": "Pollo, quinoa y verduras.",
      "precio": 6500,
      "precio_oferta": null,
      "precio_final": 6500,
      "disponible": true,
      "activo": true,
      "categoria_id": 1,
      "categoria": "Bowls",
      "stock": 10
    }
  }
}
```

### S19 · DELETE /productos/{id}

- **Destino y acceso:** inventory; Administrador o Dueño.
- **Regla:** Desactivación lógica idempotente, no DELETE SQL. Ocultar en catálogo, combos afectados no disponibles, sin borrar referencias ni compromisos de reservas. No se agrega operación de reactivación.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": null,
    "headers": {
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 1
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 1,
      "activo": false
    }
  }
}
```

### S06 · GET /comunas

- **Destino y acceso:** orders; Anónimo; datos públicos.
- **Regla:** Público, dirigido a orders. Solo comunas habilitadas con tarifa oficial. Referencia pequeña preconfigurada, sin paginación/mantenedor. Clients puede consultar este mismo contrato por red privada para validar y guardar su perfil; no hay JOIN entre bases.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {}
  },
  "respuesta": {
    "status": 200,
    "body": [
      {
        "id": 1,
        "nombre": "Comuna Demo",
        "ciudad": "Ciudad Demo",
        "region": "Región Demo",
        "costo_envio": 1500
      }
    ]
  }
}
```

### S20 · POST /ordenes

- **Destino y acceso:** orders; Cliente con sesión y correo verificado; comprador obtenido de la sesión.
- **Regla:** Cliente verificado desde sesión. Dirección y al menos un ítem; XOR producto_id/combo_id y cantidad positiva. Validar caja/cajero/comuna; I02 comprador, I05 reserva y nombres/precios oficiales; persistir snapshots. No aceptar cliente_id, estado, descuento o total como autoridad.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "direccion": {
        "calle": "Calle Demo",
        "numero": "100",
        "departamento": null,
        "comuna_id": 1
      },
      "items": [
        {
          "producto_id": 1,
          "cantidad": 2
        }
      ]
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 101,
      "estado": "pendiente",
      "version": 1,
      "reserva_id": 701,
      "vence_en": "2026-10-24T14:15:00Z",
      "subtotal": 13000,
      "descuento": 0,
      "costo_envio": 1500,
      "total": 14500,
      "moneda": "CLP"
    }
  }
}
```

### S21 · GET /ordenes

- **Destino y acceso:** orders; GraphQL con identidad técnica y usuario verificado. Cliente: propios; Administrador: gestión; Cajero: caja asignada; Despacho: cola y campos operativos.
- **Regla:** Privado G01/G05. Estado/fechas de creación opcionales. Contexto decide propios/caja/gestión/operativa de Despacho; no cliente_id/caja_id para ampliar alcance. Despacho ordena pago confirmado+ID ascendentes; resto creación+ID descendentes.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "estado": "pagado",
      "desde": "2026-10-24",
      "hasta": "2026-10-24",
      "pagina": 1,
      "limite": 20
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 101,
          "estado": "pagado",
          "moneda": "CLP",
          "total": 14500,
          "creado_en": "2026-10-24T14:00:00Z",
          "pagado_en": "2026-10-24T14:04:00Z",
          "venta_id": 301
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

### S22 · GET /ordenes/{id}

- **Destino y acceso:** orders; GraphQL con identidad técnica y usuario verificado. Cliente propietario; Administrador; Cajero de su caja; Despacho según finalidad operativa.
- **Regla:** Primero autorizar. Cliente ajeno/inexistente: mismo 404. Orders devuelve campos por finalidad; Despacho sin precios/totales/venta/comprobante, Cajero sin dirección/teléfono por defecto. Enriquecimiento de catálogo/dinero se hace fuera de este contrato, por APIs.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "historial_pagina": 1,
      "historial_limite": 20
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "cliente_id": 7,
      "estado": "pagado",
      "version": 2,
      "moneda": "CLP",
      "subtotal": 13000,
      "descuento": 0,
      "costo_envio": 1500,
      "total": 14500,
      "creado_en": "2026-10-24T14:00:00Z",
      "actualizado_en": "2026-10-24T14:04:00Z",
      "pagado_en": "2026-10-24T14:04:00Z",
      "vence_en": "2026-10-24T14:15:00Z",
      "venta_id": 301,
      "cliente": {
        "nombres": "Cliente",
        "apellidos": "Demo",
        "telefono": "+56900000000"
      },
      "direccion": {
        "calle": "Calle Demo",
        "numero": "100",
        "departamento": null,
        "comuna_id": 1,
        "comuna": "Comuna Demo"
      },
      "lineas": [
        {
          "id": 501,
          "producto_id": 1,
          "combo_id": null,
          "nombre": "Bowl Proteico Demo",
          "cantidad": 2,
          "precio_unitario": 6500,
          "subtotal": 13000
        }
      ],
      "historial": {
        "items": [
          {
            "estado": "pendiente",
            "fecha": "2026-10-24T14:00:00Z"
          },
          {
            "estado": "pagado",
            "fecha": "2026-10-24T14:04:00Z"
          }
        ],
        "paginacion": {
          "pagina": 1,
          "limite": 20,
          "total": 2
        }
      },
      "comprobante": {
        "id": 601,
        "venta_id": 301,
        "numero": "DEMO-000301",
        "estado_emision": "emitido",
        "estado_envio": "simulado"
      }
    }
  }
}
```

### S23 · POST /ordenes/{id}/cancelaciones

- **Destino y acceso:** orders; Cliente propietario o Administrador.
- **Regla:** Motivo obligatorio; version opcional como precondición. CAS servidor siempre. Solo pendiente/pagado; liberar o restituir según resultado real y coordinar devolución si hubo cobro. Preparación que ganó antes produce 409.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "motivo": "Cancelación de prueba solicitada antes de preparar.",
      "version": 2
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "cancelado",
      "version": 3,
      "causa_cancelacion": "antes_preparacion",
      "reembolso_id": 401
    }
  }
}
```

### S24 · POST /ordenes/{id}/preparacion

- **Destino y acceso:** orders; Despacho.
- **Regla:** Despacho; version opcional, comprobación atómica obligatoria. Validar estado previo según tabla de transiciones y registrar actor/fecha. No aceptar un estado final arbitrario enviado por el navegador.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "version": 2
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "preparando",
      "version": 3
    }
  }
}
```

### S25 · POST /ordenes/{id}/envios

- **Destino y acceso:** orders; Despacho.
- **Regla:** Despacho; version opcional, comprobación atómica obligatoria. Validar estado previo según tabla de transiciones y registrar actor/fecha. No aceptar un estado final arbitrario enviado por el navegador.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "version": 3
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "enviado",
      "version": 4
    }
  }
}
```

### S26 · POST /ordenes/{id}/entregas

- **Destino y acceso:** orders; Despacho.
- **Regla:** Despacho; version opcional, comprobación atómica obligatoria. Validar estado previo según tabla de transiciones y registrar actor/fecha. No aceptar un estado final arbitrario enviado por el navegador.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "version": 4
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "entregado",
      "version": 5
    }
  }
}
```

### S27 · GET /ordenes/{id}/orden-despacho

- **Destino y acceso:** orders; Despacho; campos mínimos necesarios.
- **Regla:** Respuesta real es HTML imprimible, no el objeto JSON ilustrativo. Solo finalidad operativa y pago confirmado; no precios/secretos. GET no marca impresión ni preparación.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "Authorization": "Bearer <access_token>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "content_type": "text/html; charset=utf-8",
      "documento": "Orden imprimible ficticia con líneas y dirección autorizadas."
    }
  }
}
```

### S28 · GET /cajas

- **Destino y acceso:** orders; Administrador; Cajero: solo su caja.
- **Regla:** Referencia única: Administrador ve Web y asignación; Cajero solo su caja. Sin apertura/cierre ni selección entre múltiples cajas.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": [
      {
        "id": 1,
        "nombre": "Web",
        "cajero_id": 20,
        "habilitada": true
      }
    ]
  }
}
```

### S29 · PATCH /cajas/{id}

- **Destino y acceso:** orders; Administrador.
- **Regla:** Administrador; validar en I03 cuenta habilitada con rol cajero. No reasignar el cajero histórico de ventas/transacciones previas.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "cajero_id": 20
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 1
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 1,
      "nombre": "Web",
      "cajero_id": 20,
      "habilitada": true
    }
  }
}
```

### S30 · GET /reportes/ventas

- **Destino y acceso:** orders; GraphQL con identidad técnica y usuario Administrador o Dueño; datos personales mínimos.
- **Regla:** Privado G06. Ventas por fecha de registro, incluidos registros luego cancelados; no borrar/restar filas por reembolso. No calcula totales del proveedor: I17 los aporta; evita descontar devoluciones dos veces.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "desde": "2026-10-24",
      "hasta": "2026-10-24",
      "pagina": 1,
      "limite": 20
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "cantidad_ventas": 1,
      "ventas": {
        "items": [
          {
            "id": 301,
            "pedido_id": 101,
            "fecha": "2026-10-24T14:04:00Z",
            "estado_pedido": "pagado",
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

### S31 · POST /ventas/{id}/comprobantes

- **Destino y acceso:** orders; Cajero de la caja de la venta.
- **Regla:** Emisión automática al registrar venta; endpoint de recuperación del Cajero. Una boleta por venta; reintentar no crea otro número ni otra venta. Si ya existe, devuelve ese recurso.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {},
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 301
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 601,
      "venta_id": 301,
      "numero": "DEMO-000301",
      "estado_emision": "emitido",
      "estado_envio": "simulado"
    }
  }
}
```

### S32 · GET /ventas/{id}/comprobante

- **Destino y acceso:** orders; Cliente propietario; Cajero de su caja; Administrador para gestión.
- **Regla:** Respuesta real es documento HTML descargable; el JSON describe el ejemplo. Cliente propietario/Cajero de caja/Administrador. No constituye integración tributaria externa; es comprobante académico persistido.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "Authorization": "Bearer <access_token>"
    },
    "path": {
      "id": 301
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "content_type": "text/html; charset=utf-8",
      "documento": "Comprobante de compra ficticio DEMO-000301."
    }
  }
}
```

### S33 · POST /ventas/{id}/comprobante/envios

- **Destino y acceso:** orders; Cajero de la caja de la venta.
- **Regla:** Destinatario verificado conservado de la compra; no email arbitrario en body. Enviar mediante adaptador simulado, conservar intento/error. Repetir la misma clave no envía otra vez.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {},
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 301
    }
  },
  "respuesta": {
    "status": 202,
    "body": {
      "comprobante_id": 601,
      "estado_envio": "simulado",
      "mensaje_id": "correo-demo-601"
    }
  }
}
```

### S34 · POST /pagos

- **Destino y acceso:** payments; Cliente propietario con reserva vigente o Cajero de la caja asignada.
- **Regla:** Monto/caja/moneda/propietario/vence_en desde I10. Reutilizar intento pendiente vigente; un rechazo permite otro intento explícito con otra clave. URL relativa al origen público del gateway, nunca hostname privado. Sin aprobar desde frontend.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "orden_id": 101
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 201,
      "pedido_id": 101,
      "estado": "pendiente",
      "monto": 14500,
      "moneda": "CLP",
      "checkout_url": "/simulador/pagos/checkout/<token-efimero>"
    }
  }
}
```

### S35 · GET /pagos/{id}

- **Destino y acceso:** payments; Cliente propietario; Cajero de su caja; Administrador para evaluar devoluciones.
- **Regla:** Solo alcance propio/caja/gestión autorizados. Sin credenciales, firmas, datos bancarios o payload crudo del proveedor.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "Authorization": "Bearer <access_token>"
    },
    "path": {
      "id": 201
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 201,
      "pedido_id": 101,
      "estado": "aprobado",
      "monto": 14500,
      "moneda": "CLP",
      "creado_en": "2026-10-24T14:00:00Z",
      "actualizado_en": "2026-10-24T14:04:00Z"
    }
  }
}
```

### S36 · POST /webhooks/pagos/{proveedor}

- **Destino y acceso:** payments; Proveedor autenticado por su mecanismo de integración; no depende de una sesión de usuario.
- **Regla:** proveedor=simulado; firma HMAC y timestamp, sin sesión humana. Solo acepta avisos de pago; las devoluciones se verifican por la respuesta y consulta al simulador, sin otro webhook. Verificar estado en M02, IDs y monto/moneda, deduplicar evento/transacción y aplicar el resultado durante la solicitud. Devuelve 200 al completar, o error de dependencia para reenviar el mismo aviso. Un evento procesado devuelve 200 y duplicado=true, sin repetir stock/venta/dinero.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "evento_id": "evento-demo-201",
      "tipo": "pago",
      "transaccion_id": "transaccion-demo-201",
      "estado": "aprobado",
      "monto": 14500,
      "moneda": "CLP"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Proveedor-Timestamp": "<timestamp-UTC>",
      "X-Proveedor-Firma": "<firma-del-cuerpo>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "proveedor": "simulado"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "recibido": true,
      "duplicado": false
    }
  }
}
```

### S37 · POST /solicitudes-reembolso

- **Destino y acceso:** payments; Cliente propietario; pago verificado.
- **Regla:** Texto requerido, sin archivos/URL de evidencia. Pedido preparando/enviado/entregado con pago; una solicitud/proceso activo. Permitir nueva tras rechazo con nuevos antecedentes; saldo íntegramente devuelto produce conflicto.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "pedido_id": 101,
      "motivo": "El pedido presenta el problema descrito en estos antecedentes de prueba."
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 501,
      "pedido_id": 101,
      "motivo": "El pedido presenta el problema descrito en estos antecedentes de prueba.",
      "estado": "pendiente",
      "creado_en": "2026-10-24T14:04:00Z",
      "decision": null,
      "reembolso": null
    }
  }
}
```

### S38 · GET /solicitudes-reembolso

- **Destino y acceso:** payments; Cliente: propias; Administrador: gestión.
- **Regla:** Cliente solo propias; Administrador gestión. Estado opcional pendiente/aprobada/rechazada; fechas opcionales con validación común.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "estado": "pendiente",
      "pagina": 1,
      "limite": 20
    },
    "headers": {
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "id": 501,
          "pedido_id": 101,
          "motivo": "El pedido presenta el problema descrito en estos antecedentes de prueba.",
          "estado": "pendiente",
          "creado_en": "2026-10-24T14:04:00Z",
          "decision": null,
          "reembolso": null
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

### S39 · GET /solicitudes-reembolso/{id}

- **Destino y acceso:** payments; Cliente propietario o Administrador.
- **Regla:** Detalle textual, decisión con razón y proceso financiero; no archivos. Solo propietario/Administrador. Persistir toda decisión e intentos.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "Authorization": "Bearer <access_token>"
    },
    "path": {
      "id": 501
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 501,
      "pedido_id": 101,
      "motivo": "El pedido presenta el problema descrito en estos antecedentes de prueba.",
      "estado": "pendiente",
      "creado_en": "2026-10-24T14:04:00Z",
      "decision": null,
      "reembolso": null
    }
  }
}
```

### S40 · POST /solicitudes-reembolso/{id}/decisiones

- **Destino y acceso:** payments; Solo Administrador.
- **Regla:** Solo Administrador, solicitud pendiente/versionada. Rechazar registra estado rechazada sin devolución; aprobar valida pago/saldo y coordina I18 antes de devolver. Si preparar aún es actual, cancelar sin stock; enviado/entregado continúa. Conciliación persistida evita decidir dos veces.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "decision": "aprobar",
      "motivo": "Aprobación de prueba con devolución completa."
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 501
    }
  },
  "respuesta": {
    "status": 202,
    "body": {
      "id": 501,
      "estado": "aprobada",
      "reembolso": {
        "id": 401,
        "pedido_id": 101,
        "pago_id": 201,
        "estado": "pendiente",
        "monto_solicitado": 14500,
        "monto_devuelto": 0,
        "moneda": "CLP",
        "causa": "excepcional",
        "solicitud_id": 501,
        "reintentable": false
      }
    }
  }
}
```

### S42 · POST /reembolsos/{id}/reintentos

- **Destino y acceso:** payments; Administrador; causa/autorización original válidas.
- **Regla:** Administrador; no nueva aprobación ni cambio de importe/causa. Si falló definitivamente, crear intento financiero ligado al mismo reembolso. Si resultado incierto, consultar primero al proveedor con la referencia existente; no generar otra devolución. Si ya completado, devolver el resultado sin repetirlo.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {},
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 401
    }
  },
  "respuesta": {
    "status": 202,
    "body": {
      "id": 401,
      "pedido_id": 101,
      "pago_id": 201,
      "estado": "pendiente",
      "monto_solicitado": 14500,
      "monto_devuelto": 0,
      "moneda": "CLP",
      "causa": "excepcional",
      "solicitud_id": 501,
      "reintentable": false
    }
  }
}
```

### S41 · POST /graphql

- **Destino y acceso:** graphql; Anónimo para catálogo público; sesión y permisos por operación/recurso/campo para el resto.
- **Regla:** Contrato y seis ejemplos completos en contratos-graphql.md. El rol real viene de Auth; POST no autoriza todos los campos. Datos+errors parciales y límites acordados.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operationName": "MiPerfil",
      "query": "query MiPerfil { perfil { id rol } }",
      "variables": {}
    },
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer <access_token>"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "data": {
        "perfil": {
          "id": "10",
          "rol": "cliente"
        }
      }
    }
  }
}
```

### I01 · POST /introspect

- **Destino y acceso:** auth; solo el API Gateway con X-Gateway-Secret y X-Gateway-Auth-Secret obtenidos de Vault.
- **Entrada:** `{token: "<access_token>"}`.
- **Salida 200:** `{active, user_id, username, roles, cliente_id, email_verificado_at, expires_at}` si está vigente. `{active:false}` si está revocada/vencida o la cuenta cambió.
- Auth comprueba su sesión hasheada y consulta I03 para confirmar cuenta y versión. Los servicios no reciben este token; utilizan el contexto verificado del gateway.

### I02 · GET /interno/clientes/{id}

- **Destino y acceso:** clients; orders, con finalidad y contexto de usuario autorizados.
- **Regla:** Orders para snapshot del comprador/comprobante; finalidad y usuario verificados. Sin fecha de nacimiento, sexo, hashes o códigos.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    },
    "path": {
      "id": 7
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 7,
      "nombres": "Cliente",
      "apellidos": "Demo",
      "rut": "11111111-1",
      "email": "cliente@example.com",
      "telefono": "+56900000000",
      "correo_verificado": true
    }
  }
}
```

### I03 · GET /interno/usuarios/{id}

- **Destino y acceso:** clients; orders; solo datos mínimos para esa comprobación.
- **Regla:** Orders valida cajero para caja; sin credenciales ni perfil personal no necesario.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    },
    "path": {
      "id": 20
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 20,
      "rol": "cajero",
      "activo": true
    }
  }
}
```

### I04 · POST /interno/catalogo/consultas

- **Destino y acceso:** inventory; orders para precios; GraphQL Gateway para catálogo público. El lote tiene un máximo.
- **Regla:** Lote hasta 50 referencias tipo+ID. Orders recibe precios autorizados; GraphQL campos públicos según contexto. Retirado/inexistente: encontrado=false, no sustituir historia. Fuente caída: error, no encontrado=false.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "items": [
        {
          "tipo": "producto",
          "id": 1
        }
      ]
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "tipo": "producto",
          "id": 1,
          "encontrado": true,
          "nombre": "Bowl Proteico Demo",
          "precio_final": 6500,
          "disponible": true
        }
      ]
    }
  }
}
```

### I05 · POST /interno/reservas

- **Destino y acceso:** inventory; orders; referencia de operación e identidad verificadas.
- **Regla:** Solo orders. Todo o nada; resolver combos, disponibilidad libre y nombres/precios oficiales por identidad. Vence 15 min con reloj inventory. `limite_subtotal` interno opcional (por defecto 2147483647): orders envía el máximo menos el envío histórico; inventory valida la suma antes de reservar y devuelve 422 sin retener unidades si se excede. Misma operación recupera la misma reserva; ningún precio del navegador es autoridad.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "checkout-demo-101",
      "items": [
        {
          "producto_id": 1,
          "cantidad": 2
        }
      ]
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 201,
    "body": {
      "id": 701,
      "operacion_id": "checkout-demo-101",
      "estado": "activa",
      "vence_en": "2026-10-24T14:15:00Z",
      "moneda": "CLP",
      "lineas": [
        {
          "producto_id": 1,
          "combo_id": null,
          "nombre": "Bowl Proteico Demo",
          "cantidad": 2,
          "precio_unitario": 6500,
          "subtotal": 13000
        }
      ]
    }
  }
}
```

### I06 · GET /interno/reservas/{id}

- **Destino y acceso:** inventory; orders; solo reservas vinculadas a operaciones bajo su autoridad.
- **Regla:** Orders; estados activa/consumida/liberada/expirada/restituida. Devuelve vencimiento y referencia para recuperar operaciones inciertas; no lee otras bases.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    },
    "path": {
      "id": 701
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 701,
      "operacion_id": "checkout-demo-101",
      "estado": "activa",
      "vence_en": "2026-10-24T14:15:00Z",
      "moneda": "CLP",
      "lineas": [
        {
          "producto_id": 1,
          "combo_id": null,
          "nombre": "Bowl Proteico Demo",
          "cantidad": 2,
          "precio_unitario": 6500,
          "subtotal": 13000
        }
      ]
    }
  }
}
```

### I07 · POST /interno/reservas/{id}/consumos

- **Destino y acceso:** inventory; orders, después de recibir un pago verificado.
- **Regla:** Orders tras pago verificado; consumir activa no vencida una vez, contra liberación/expiración atómicas. Vencida no puede consumirse de nuevo.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "operacion-demo-101",
      "orden_id": 101,
      "motivo": "operación autorizada de prueba"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 701
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 701,
      "estado": "consumida"
    }
  }
}
```

### I08 · POST /interno/reservas/{id}/liberaciones

- **Destino y acceso:** inventory; orders o proceso de vencimiento autorizado.
- **Regla:** Orders/proceso autorizado: liberar solo unidades reservadas no consumidas por cancelación/vencimiento/checkout fallido. No restituye consumo.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "operacion-demo-101",
      "orden_id": 101,
      "motivo": "operación autorizada de prueba"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 701
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 701,
      "estado": "liberada"
    }
  }
}
```

### I09 · POST /interno/reservas/{id}/restituciones

- **Destino y acceso:** inventory; orders; operación de cancelación autorizada.
- **Regla:** Orders por cancelación normal pagada antes de preparar. Referencia de cancelación única; nunca en excepción administrativa durante preparación.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "operacion-demo-101",
      "orden_id": 101,
      "motivo": "operación autorizada de prueba"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 701
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 701,
      "estado": "restituida"
    }
  }
}
```

### I10 · GET /interno/ordenes/{id}/cobro

- **Destino y acceso:** orders; payments; identidad técnica y contexto de operación autorizados.
- **Regla:** Payments obtiene monto/propiedad/estado oficial y causa de cancelación si existe. Validar contexto de la operación; no exponer dirección/RUT innecesarios.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "cliente_id": 7,
      "caja_id": 1,
      "cajero_id": 20,
      "estado": "pendiente",
      "total": 14500,
      "moneda": "CLP",
      "reserva_id": 701,
      "vence_en": "2026-10-24T14:15:00Z"
    }
  }
}
```

### I11 · POST /interno/ordenes/{id}/resultados-pago

- **Destino y acceso:** orders; payments; referencia del intento, evento, monto y moneda comprobados.
- **Regla:** Solo payments verificado. Coordinar consumo una vez, venta/recibo; si reserva vencida/cancelada, no reactivar y coordinar devolución por I14. Estado persistido/versión para recuperar; no una transacción SQL distribuida ficticia.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "pago-demo-201",
      "pago_id": 201,
      "evento_id": "evento-demo-201",
      "transaccion_id": "transaccion-demo-201",
      "estado": "aprobado",
      "monto": 14500,
      "moneda": "CLP"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "pagado",
      "venta_id": 301
    }
  }
}
```

### I12 · POST /interno/ordenes/{id}/vencimientos

- **Destino y acceso:** orders; Proceso interno de vencimiento autorizado.
- **Regla:** Reloj servidor; volver a comprobar pago/consumo/versión antes de liberar. Un consumo válido ya confirmado obliga a conciliar, no expirar o liberar de nuevo.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "vencimiento-demo-101",
      "reserva_id": 701
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "expirado"
    }
  }
}
```

### I13 · POST /interno/ordenes/{id}/resultados-reembolso

- **Destino y acceso:** orders; payments; resultado verificado de devolución.
- **Regla:** Payments informa resultado financiero confirmado. Registrar historial; no restaurar stock otra vez ni cambiar enviado/entregado por estado financiero.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "devolucion-demo-401",
      "reembolso_id": 401,
      "estado": "completado",
      "monto_devuelto": 14500,
      "moneda": "CLP"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "cancelado",
      "reembolso_id": 401
    }
  }
}
```

### I18 · POST /interno/ordenes/{id}/autorizaciones-reembolso

- **Destino y acceso:** orders; payments con identidad técnica y contexto de Administrador verificado.
- **Regla:** Solo payments, que conserva la decisión administrativa verificada. Orders verifica pago/estado/versión y registra esa referencia. Preparando se cancela sin restituir; enviado/entregado conserva estado. Repetir la misma decisión devuelve su resultado; no exige sesión humana aún vigente para recuperar una decisión ya autorizada/persistida.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "decision-demo-501",
      "solicitud_id": 501,
      "decision_id": "decision-demo-501",
      "administrador_id": 30,
      "motivo": "Aprobación excepcional de prueba."
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    },
    "path": {
      "id": 101
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "id": 101,
      "estado": "cancelado",
      "causa_cancelacion": "reembolso_excepcional",
      "stock_restituido": false
    }
  }
}
```

### I14 · POST /interno/reembolsos

- **Destino y acceso:** payments; orders para causas automáticas autorizadas; sin permiso para simular una aprobación excepcional de Administrador.
- **Regla:** Orders para cancelación pagada/pago tardío/cobro duplicado. Validar fuente, causa y saldo completo de la operación aplicable; sin importe arbitrario. Excepción aprobada usa la misma lógica interna financiera de payments.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "operacion_id": "cancelacion-demo-101",
      "orden_id": 101,
      "pago_id": 201,
      "causa": "cancelacion_pagada"
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "Idempotency-Key": "<clave-estable-de-la-operacion>"
    }
  },
  "respuesta": {
    "status": 202,
    "body": {
      "id": 401,
      "estado": "pendiente",
      "monto_solicitado": 14500,
      "moneda": "CLP"
    }
  }
}
```

### I15 · GET /interno/pagos/{id}/estado

- **Destino y acceso:** payments; orders; pago asociado a un pedido autorizado.
- **Regla:** Orders recupera resultado verificado y referencias; no reenvía cobros. Resultado incierto no se inventa como rechazado/fallido.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {},
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>"
    },
    "path": {
      "id": 201
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "pago": {
        "id": 201,
        "pedido_id": 101,
        "estado": "aprobado",
        "monto": 14500,
        "moneda": "CLP",
        "creado_en": "2026-10-24T14:00:00Z",
        "actualizado_en": "2026-10-24T14:04:00Z"
      },
      "reembolso": {
        "id": 401,
        "pedido_id": 101,
        "pago_id": 201,
        "estado": "fallido",
        "monto_solicitado": 14500,
        "monto_devuelto": 0,
        "moneda": "CLP",
        "causa": "excepcional",
        "solicitud_id": 501,
        "reintentable": true
      }
    }
  }
}
```

### I16 · POST /interno/pagos/consultas

- **Destino y acceso:** payments; GraphQL con identidad técnica y contexto verificado: Cliente propietario; Administrador; Cajero de su caja para campos financieros permitidos. Cada pedido se autoriza y solo se devuelven campos mínimos; sin payloads del proveedor.
- **Regla:** GraphQL con contexto: propietario/Administrador/Cajero de caja para campos permitidos. Hasta 50 IDs, cada uno autorizado. Cliente/Despacho no acceden a expedientes ajenos ni datos del proveedor.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "body": {
      "pedido_ids": [
        101
      ]
    },
    "headers": {
      "Content-Type": "application/json",
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "items": [
        {
          "pedido_id": 101,
          "pago": {
            "id": 201,
            "pedido_id": 101,
            "estado": "aprobado",
            "monto": 14500,
            "moneda": "CLP",
            "creado_en": "2026-10-24T14:00:00Z",
            "actualizado_en": "2026-10-24T14:04:00Z"
          },
          "reembolso": {
            "id": 401,
            "pedido_id": 101,
            "pago_id": 201,
            "estado": "fallido",
            "monto_solicitado": 14500,
            "monto_devuelto": 0,
            "moneda": "CLP",
            "causa": "excepcional",
            "solicitud_id": 501,
            "reintentable": true
          }
        }
      ]
    }
  }
}
```

### I17 · GET /interno/reportes/movimientos

- **Destino y acceso:** payments; GraphQL con identidad técnica y contexto de Administrador o Dueño; finalidad de reporte y datos personales mínimos.
- **Regla:** GraphQL Administrador/Dueño; cada movimiento por fecha propia, neto puede ser negativo. Importes acumulados como cadena decimal entera; sin doble descuento ni pagos individuales.
- **Errores:** validación/autorización comunes; 409 ante conflicto de estado/referencia cuando aplica.

```json
{
  "solicitud": {
    "query": {
      "desde": "2026-10-24",
      "hasta": "2026-10-24"
    },
    "headers": {
      "X-Gateway-Secret": "<credencial-del-consumidor>",
      "X-Authenticated-User-ID": "10",
      "X-Authenticated-User": "cliente@example.com",
      "X-Authenticated-Roles": "cliente",
      "X-Authenticated-Client-ID": "7",
      "X-Authenticated-Email-Verified": "1"
    }
  },
  "respuesta": {
    "status": 200,
    "body": {
      "total_cobrado": "14500",
      "total_devuelto": "20000",
      "neto_cobrado": "-5500",
      "moneda": "CLP",
      "zona_horaria": "America/Santiago"
    }
  }
}
```

## Proveedor de pagos simulado

Los siguientes contratos pertenecen al adaptador de pruebas, separados de los 61 contratos propios. APIs M01–M04 privadas requieren credencial de payments obtenida de Vault; M01/M03 requieren idempotencia. Solo en ambiente demo se publican M05/M06 mediante las rutas explícitas del API Gateway `/simulador/pagos/checkout/{token}` y `/simulador/pagos/checkout/{token}/resultado`. La URL de checkout se resuelve contra el origen público del gateway.

La pantalla permite aprobado/rechazado/pendiente sobre la transacción ya creada; no recibe monto, pedido o destinatario de devolución arbitrarios. El token efímero es propio de esa transacción de prueba y no una credencial de servicio. Retornos del navegador solo llevan a la vista de pedido propuesta; no cambian estado de compra. Redirección configurada/permitida en servidor, sin return_url libre del cliente.

### I19 · POST /interno/auth/credenciales

- **Destino y acceso:** clients; exclusivamente Auth con su secreto técnico.
- **Entrada:** `{username: "cliente@example.com"}`.
- **Salida privada 200:** cuenta, `password_hash`, rol, estado/verificación y `version`. Auth valida la contraseña y crea la sesión en su base. 404 si no existe; el login externo transforma ese caso en 401 genérico.
- No se publica a través del gateway ni GraphQL. Ninguna respuesta pública contiene hashes.

### M01 · POST /transacciones

Acceso: payments. Ejemplo ficticio:

```json
{
  "solicitud": {
    "operacion_id": "pago-demo-201",
    "pedido_id": 101,
    "monto": 14500,
    "moneda": "CLP",
    "retorno_id": "detalle-pedido"
  },
  "respuesta": {
    "transaccion_id": "transaccion-demo-201",
    "estado": "pendiente",
    "checkout_url": "/simulador/pagos/checkout/<token-efimero>"
  }
}
```

### M02 · GET /transacciones/{id}

Acceso: payments. Ejemplo ficticio:

```json
{
  "solicitud": {},
  "respuesta": {
    "transaccion_id": "transaccion-demo-201",
    "pedido_id": 101,
    "estado": "aprobado",
    "monto": 14500,
    "moneda": "CLP"
  }
}
```

### M03 · POST /transacciones/{id}/reembolsos

Acceso: payments. Ejemplo ficticio:

```json
{
  "solicitud": {
    "operacion_id": "devolucion-demo-401",
    "monto": 14500,
    "moneda": "CLP"
  },
  "respuesta": {
    "reembolso_id": "refund-demo-401",
    "estado": "completado",
    "monto_devuelto": 14500,
    "moneda": "CLP"
  }
}
```

### M04 · GET /reembolsos/{id}

Acceso: payments. Ejemplo ficticio:

```json
{
  "solicitud": {},
  "respuesta": {
    "reembolso_id": "refund-demo-401",
    "estado": "completado",
    "monto_devuelto": 14500,
    "moneda": "CLP"
  }
}
```

### M05 · GET /checkout/{token}

Acceso: pantalla de prueba con token efímero. Ejemplo ficticio:

```json
{
  "solicitud": {},
  "respuesta": {
    "content_type": "text/html",
    "contenido": "Opciones aprobado, rechazado y pendiente; indicadores de simulación."
  }
}
```

### M06 · POST /checkout/{token}/resultado

Acceso: pantalla de prueba con token efímero. Ejemplo ficticio:

```json
{
  "solicitud": {
    "resultado": "aprobado"
  },
  "respuesta": {
    "status": 303,
    "retorno": "URL permitida de la vista de detalle de pedido"
  }
}
```

### Avisos y escenarios del simulador

El simulador invoca S36 con evento_id único, tipo pago/reembolso, referencia de transacción/devolución, resultado, monto y moneda. Cabeceras: X-Proveedor-Timestamp (segundos UTC) y X-Proveedor-Firma (HMAC-SHA256 de timestamp + punto + bytes del cuerpo usando la referencia de secreto del simulador). Validar tolerancia inicial de cinco minutos y comparar en tiempo constante. En un aviso diferido se firma al enviarlo, conservando el ID/fecha del hecho financiero; no falsificar el vencimiento del pedido. Payments además consulta M02/M04 antes de dar efectos al resultado.

Preparar fixtures/controles privados para repetición, entrega tardía, caída de comunicación y devolución fallida. Repetir evento no cambia saldo/venta/stock; en resultado incierto consultar antes de reintentar con su referencia. Una devolución definitivamente fallida permite otro intento técnico bajo el mismo reembolso autorizado; no otro importe parcial. El simulador persiste transacciones/eventos suficientes para conciliar tras reinicio; no reemplaza las bases reales de inventory/orders/clients/payments.

### Correo simulado y credenciales simbólicas

No se implementa email real en esta etapa ni se pide un dominio. Conservar una interfaz de adaptador `enviar(mensaje_id, destino_verificado, asunto, cuerpo)` y resultado `{mensaje_id, estado: simulado}` o error controlado. Verificación y comprobantes siguen funcionando con mensajes de prueba consultables por el operador autorizado, separados de logs generales; no publicar códigos/token en respuestas anónimas ni afirmar entrega real. La implementación actual imprime correo en consola: sigue siendo una brecha de protección/verificabilidad, no una API real terminada.

Solo se documentan referencias simbólicas de Vault: gateway→auth/clients/inventory/orders/payments/graphql; GraphQL→clients/inventory/orders/payments; orders→clients/inventory/payments; clients→orders para comunas; payments→orders/simulador; firma simulador→payments. Auth→clients para credenciales y versión de cuenta. Cada consumidor obtiene su propia credencial limitada a rutas/operaciones, con cambio/revocación manual en Vault y reinicio de los servicios para cargar la nueva identidad. No escribir valores en repo, frontend o logs. Los archivos de variables de entorno los modifica exclusivamente el usuario.

## Recuperación, despliegue y evidencia pendiente

- Nueva compra: validar Cliente/caja/comuna; I05 devuelve reserva/precios/snapshots oficiales; persistir pedido. Si el guardado falla de forma confirmada, liberar reserva con referencia; ante resultado incierto consultar/reintentar la misma operación antes de compensar.
- Pago: registrar evento/ref verificados; coordinar I07 e I11 y persistir los pasos. Si vence/cancela sin consumo válido, mantener su estado y devolver lo cobrado. Consumo ya aceptado que ganó la carrera requiere conciliación, no liberar ni expirar a ciegas.
- Excepción: S40 conserva decisión; I18 confirma efecto operativo idempotente antes de devolver. Si la respuesta se pierde, repetir/consultar la misma referencia. Al registrar dinero no volver a cancelar ni a mover stock.
- Códigos/mensajes/fechas/claves de idempotencia son contratos objetivo; aplicar migraciones a los DTO y consumidores actuales. El ejemplo de clave/código/token es un marcador, no una credencial utilizable.
- Adaptadores simulados son elección explícita para esta etapa, no una prueba de inaccesibilidad de un proveedor. M10 p.18 pide sandbox cuando está disponible y justificar una alternativa de prueba cuando la integración no es accesible. La justificación y sus límites se explican en la entrega, sin declarar integración real ni cumplimiento automático de ese criterio.
- Faltan UML editables, matriz formal requisito/pantalla/servicio, resolvers/servicios, pruebas de contratos/seguridad/concurrencia/fallos/carga y despliegue reproducible. No marcar esos entregables completos por esta documentación. Analítica/gRPC quedan sujetos a ADR y mediciones, sin necesidad inventada para un reporte básico.
