// Adaptado del código visible y las capturas de la clase del 04-11-2026.
workspace "Fit Express" "Plataforma de venta de bowls, snacks y combos" {
    !identifiers hierarchical
    model {
        // ========================================
        // 1. ACTORES DEL SISTEMA
        // ========================================

        visitante = person "Visitante" "Persona que consulta el catálogo público sin iniciar sesión."

        cliente = person "Cliente" "Persona autenticada que compra productos y gestiona sus pedidos."

        operador = person "Operador" "Personal autorizado: Administrador, Cajero, Despacho o Dueño, cada uno con permisos propios."

        // ========================================
        // 2. SISTEMA PRINCIPAL
        // ========================================

        sistema = softwareSystem "Fit Express" "Sistema que integra catálogo de alimentos, clientes, pedidos, despacho, pagos y devoluciones." {
            tags "SistemaEvaluado"

            // CAPA DE PRESENTACION
            frontend = container "Frontend responsivo" "Interfaz web para visitantes, clientes y operadores." "Aplicación web" {
                tags "Frontend"
            }

            // PUNTO DE ENTRADA
            apiGateway = container "API Gateway" "Punto de entrada al backend; enruta peticiones y aplica controles configurados." "Servicio HTTP" {
                tags "Gateway"

                httpEntry = component "Adaptador HTTP" "Recibe solicitudes y genera respuestas HTTP." "Módulo de entrada" {
                    tags "EntradaC3"
                }

                identityFilter = component "Filtro acceso" "Distingue rutas públicas y aplica identidad, roles y límites configurados." "Módulo de seguridad" {
                    tags "ControlC3"
                }

                routeDispatcher = component "Despachador de rutas" "Dirige cada solicitud al backend definido por el contrato." "Módulo de enrutamiento" {
                    tags "AplicacionC3"
                }

                errorMapper = component "Traductor de errores" "Convierte fallos controlados en respuestas consistentes sin revelar detalles sensibles." "Módulo de errores" {
                    tags "ErrorC3"
                }
            }

            // SEGURIDAD
            authService = container "Auth Service" "Autentica usuarios y suministra o valida identidad según el contrato implementado." "Servicio de identidad" {
                tags "Seguridad"

                identityApi = component "API de identidad" "Atiende login, introspección y cierre de sesión del gateway autorizado." "API interna" {
                    tags "EntradaC3"
                }

                sessionManager = component "Gestor de sesiones" "Controla vigencia, revocación y versión de cuenta de las sesiones." "Servicio de identidad" {
                    tags "AplicacionC3"
                }

                credentialVerifier = component "Verificador de credenciales" "Comprueba contraseña y habilitación sin exponer valores sensibles al cliente." "Servicio de validación" {
                    tags "ControlC3"
                }

                identityRepository = component "Repositorio de identidades" "Persiste sesiones y consulta cuentas autorizadas mediante la API de clients." "Acceso a datos"

                secretClient = component "Cliente de secretos" "Obtiene material secreto autorizado para operaciones de identidad." "Adaptador de integración"
            }

            secretManager = container "Administrador de secretos" "Gestiona secretos y los entrega exclusivamente a consumidores autorizados." "Gestor de secretos" {
                tags "Seguridad"
            }

            // SUBSISTEMAS PRIVADOS
            inventory = container "inventory" "Gestiona disponibilidad, catálogo de alimentos, combos y reservas de stock." "Servicio privado" {
                tags "Privado"
            }

            orders = container "orders" "Gestiona el ciclo de vida de los pedidos, despacho, ventas y comprobantes." "Servicio privado" {
                tags "Privado"

                ordersApi = component "API de pedidos" "Recibe solicitudes del gateway y consultas privadas de pedidos." "API interna" {
                    tags "EntradaC3"
                }

                accessPolicy = component "Política de acceso a pedidos" "Restringe operaciones por rol, caja y pertenencia del recurso." "Reglas de autorización" {
                    tags "ControlC3"
                }

                idempotency = component "Control de idempotencia" "Detecta reintentos duplicados de operaciones críticas." "Regla de negocio" {
                    tags "ControlC3"
                }

                orderWorkflow = component "Servicio de pedidos" "Coordina reglas, cambios de estado, despacho y dependencias del pedido." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }

                inventoryAdapter = component "Adaptador de inventario" "Consulta disponibilidad y solicita reserva y movimientos de stock." "Adaptador privado"

                paymentAdapter = component "Adaptador de pagos" "Solicita devoluciones autorizadas a payments." "Adaptador privado"

                orderRepository = component "Repositorio de pedidos" "Persiste pedidos, ventas, comprobantes y claves de operación cuando corresponda." "Acceso a datos"
            }

            clients = container "clients" "Gestiona perfiles de clientes, cuentas, roles y verificación de correo." "Servicio privado" {
                tags "Privado"
            }

            payments = container "payments" "Gestiona estados de pago, cobros verificados y devoluciones." "Servicio privado" {
                tags "Privado"
            }

            // ALMACENES DE DATOS
            dbInventory = container "Datos de inventario" "Persistencia del subsistema inventory." "Almacén de datos" {
                tags "BaseDatos"
            }

            dbOrders = container "Datos de pedidos" "Persistencia del subsistema orders." "Almacén de datos" {
                tags "BaseDatos"
            }

            dbClients = container "Datos de clientes" "Persistencia del subsistema clients." "Almacén de datos" {
                tags "BaseDatos"
            }

            dbPayments = container "Datos de pagos" "Persistencia del subsistema payments." "Almacén de datos" {
                tags "BaseDatos"
            }

            dbIdentity = container "Datos de identidad" "Persistencia de sesiones y versiones de cuenta; hashes de contraseña en clients." "Almacén de datos" {
                tags "BaseDatos"
            }

            // AGREGACION GRAPHQL
            graphqlGateway = container "GraphQL Gateway" "Expone una API de consulta y agrega información de subsistemas autorizados." "Servicio GraphQL" {
                tags "Gateway"

                graphqlEndpoint = component "Endpoint GraphQL" "Recibe operaciones GraphQL por la ruta publicada." "Adaptador GraphQL" {
                    tags "EntradaC3"
                }

                queryValidator = component "Validador de consultas" "Valida esquema y límites de complejidad configurados." "Validación GraphQL" {
                    tags "ControlC3"
                }

                fieldAccess = component "Política de acceso a campos" "Comprueba permisos para campos y recursos solicitados." "Modelo de autorización" {
                    tags "ControlC3"
                }

                resolvers = component "Resolvers de negocio" "Resuelve campos y coordina obtención de datos autorizados." "Resolvers GraphQL" {
                    tags "AplicacionC3"
                }

                serviceConnectors = component "Conectores de subsistemas" "Consulta inventory, orders, clients y payments por sus contratos internos." "Adaptadores de integración"

                responseComposer = component "Compositor de respuestas" "Conserva errores y evita presentar fallos parciales como datos completos." "Política de resultados"
            }

        }
        // Adaptación al caso: el proveedor simulado se muestra fuera del núcleo comercial.
        proveedor = softwareSystem "Proveedor de pagos simulado" "Adaptador de pruebas implementado por el equipo; mantiene sus propias transacciones y datos." {
            tags "SistemaExterno"
        }

        // ========================================
        // 3. RELACIONES DEL C1
        // ========================================

        visitante -> sistema "Consulta productos publicados"
        cliente -> sistema "Consulta productos y gestiona sus pedidos"
        operador -> sistema "Administra catálogo y operaciones autorizadas"

        // ========================================
        // 4. ACTORES HACIA FRONTEND
        // ========================================

        visitante -> sistema.frontend "Consulta el catálogo" "Navegador web"
        cliente -> sistema.frontend "Consulta y gestiona sus pedidos" "Navegador web"
        operador -> sistema.frontend "Gestiona operaciones autorizadas" "Navegador web"

        // ========================================
        // 5. ENTRADA AL BACKEND
        // ========================================

        // C3 - Frontend
        sistema.frontend -> sistema.apiGateway.httpEntry "Invoca funciones del backend" "HTTP"
        sistema.frontend -> sistema.apiGateway "Envía solicitudes de la interfaz" "HTTP"

        // ========================================
        // 6. SEGURIDAD Y SECRETOS
        // ========================================

        // C3 - API Gateway
        sistema.apiGateway.httpEntry -> sistema.apiGateway.identityFilter "Solicita comprobación de acceso"
        sistema.apiGateway.identityFilter -> sistema.authService.identityApi "Valida identidad y sesiones" "HTTP/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.routeDispatcher "Permite una ruta pública o una solicitud autorizada"
        sistema.apiGateway.routeDispatcher -> sistema.inventory "Enruta operaciones de inventario" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.orders.ordersApi "Enruta y despacha operaciones de pedidos" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.clients "Enruta operaciones de clientes" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.payments "Enruta operaciones de pagos" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway.graphqlEndpoint "Enruta y despacha consultas GraphQL" "HTTP/GraphQL"
        sistema.apiGateway.routeDispatcher -> sistema.authService.identityApi "Despacha login y logout" "HTTP/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.errorMapper "Comunica fallos de acceso controlados"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.errorMapper "Comunica fallos de comunicación controlados"

        // C3 - Auth Service
        sistema.authService.identityApi -> sistema.authService.sessionManager "Gestiona sesión o token"
        sistema.authService.sessionManager -> sistema.authService.credentialVerifier "Verifica identidad en autenticación"
        sistema.authService.credentialVerifier -> sistema.authService.identityRepository "Consulta registros autorizados"
        sistema.authService.sessionManager -> sistema.authService.identityRepository "Consulta o actualiza sesión y versión de cuenta"
        sistema.authService.identityRepository -> sistema.dbIdentity "Lee y escribe sesiones" "Acceso a datos"
        sistema.authService.identityRepository -> sistema.clients "Consulta cuentas y credenciales autorizadas" "HTTP/JSON"
        sistema.authService.credentialVerifier -> sistema.authService.secretClient "Solicita material secreto autorizado"
        sistema.authService.secretClient -> sistema.secretManager "Obtiene secretos de forma controlada" "HTTP/Vault KV"

        sistema.apiGateway -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.authService -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.payments -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.orders -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.clients -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.inventory -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"
        sistema.graphqlGateway -> sistema.secretManager "Obtiene credenciales autorizadas para integración al arrancar" "HTTP/Vault KV"

        // ========================================
        // 7. ENRUTAMIENTO A SERVICIOS PRIVADOS
        // ========================================

        sistema.apiGateway -> sistema.authService "Solicita validación de identidad o sesión" "HTTP/JSON"
        sistema.apiGateway -> sistema.inventory "Enruta consultas y operaciones de inventario" "HTTP/JSON"
        sistema.apiGateway -> sistema.orders "Enruta operaciones de pedidos" "HTTP/JSON"
        sistema.apiGateway -> sistema.clients "Enruta consultas y operaciones de clientes" "HTTP/JSON"
        sistema.apiGateway -> sistema.payments "Enruta consultas y operaciones de pagos" "HTTP/JSON"

        // ========================================
        // 8. COMUNICACIONES ENTRE SERVICIOS
        // ========================================

        // C3 - Orders
        sistema.graphqlGateway.serviceConnectors -> sistema.orders.ordersApi "Consulta pedidos permitidos" "HTTP/JSON"
        sistema.orders.ordersApi -> sistema.orders.accessPolicy "Comprueba rol y propiedad del recurso"
        sistema.orders.accessPolicy -> sistema.orders.orderWorkflow "Encamina consultas de lectura autorizadas"
        sistema.orders.accessPolicy -> sistema.orders.idempotency "Autoriza la operación de escritura"
        sistema.orders.idempotency -> sistema.orders.orderRepository "Busca operación previa por clave"
        sistema.orders.idempotency -> sistema.orders.orderWorkflow "Ejecuta solo la operación admisible"
        sistema.orders.orderWorkflow -> sistema.orders.inventoryAdapter "Consulta o reserva disponibilidad"
        sistema.orders.orderWorkflow -> sistema.orders.paymentAdapter "Solicita devolución cuando corresponde"
        sistema.orders.orderWorkflow -> sistema.orders.orderRepository "Persiste cambio de estado"
        sistema.orders.inventoryAdapter -> sistema.inventory "Invoca contrato de inventario" "HTTP/JSON"
        sistema.orders.paymentAdapter -> sistema.payments "Invoca contrato de pagos" "HTTP/JSON"
        sistema.orders.orderRepository -> sistema.dbOrders "Lee y escribe pedidos y claves de operación" "Acceso a datos"
        sistema.orders.orderWorkflow -> sistema.clients "Valida cliente y cajero del pedido" "HTTP/JSON"
        sistema.orders -> sistema.inventory "Consulta y reserva stock, si corresponde" "HTTP/JSON"
        sistema.orders -> sistema.payments "Solicita devolución de pago, si corresponde" "HTTP/JSON"
        sistema.clients -> sistema.orders "Consulta comunas habilitadas" "HTTP/JSON"
        sistema.payments -> sistema.orders.ordersApi "Consulta cobro y entrega resultados verificados" "HTTP/JSON"
        sistema.payments -> proveedor "Inicia, verifica y reembolsa cobros" "HTTP/JSON"
        proveedor -> sistema.payments "Notifica resultados firmados" "HTTP/JSON/HMAC"
        sistema.apiGateway -> proveedor "Publica checkout de prueba con token opaco" "HTTP"

        // ========================================
        // 9. ACCESO A PERSISTENCIA
        // ========================================

        sistema.inventory -> sistema.dbInventory "Lee y escribe datos de inventario" "Acceso a datos"
        sistema.orders -> sistema.dbOrders "Lee y escribe pedidos" "Acceso a datos"
        sistema.clients -> sistema.dbClients "Lee y escribe perfiles y cuentas de clientes" "Acceso a datos"
        sistema.payments -> sistema.dbPayments "Lee y escribe estados de pagos" "Acceso a datos"
        sistema.authService -> sistema.dbIdentity "Consulta y actualiza sesiones" "Acceso a datos"

        // ========================================
        // 10. AGREGACION GRAPHQL
        // ========================================

        // C3 - GraphQL Gateway
        sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Remite operaciones GraphQL" "HTTP/GraphQL"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryValidator "Verifica esquema y límites de la consulta"
        sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.fieldAccess "Entrega consulta validada"
        // Fit Express recibe contexto verificado del gateway; no llama directamente a Auth.
        sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.resolvers "Autoriza campos y recursos"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.serviceConnectors "Solicita información autorizada"
        sistema.graphqlGateway.serviceConnectors -> sistema.inventory "Consulta y conecta productos y disponibilidad" "HTTP/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.clients "Consulta y conecta perfiles autorizados" "HTTP/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.payments "Consulta y conecta pagos y devoluciones" "HTTP/JSON"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "Envía datos y errores parciales"
        sistema.apiGateway -> sistema.graphqlGateway "Enruta consultas GraphQL" "HTTP/GraphQL"
        sistema.graphqlGateway -> sistema.inventory "Agrega información de productos y stock" "HTTP/JSON"
        sistema.graphqlGateway -> sistema.orders "Agrega información autorizada de pedidos" "HTTP/JSON"
        sistema.graphqlGateway -> sistema.clients "Consulta perfiles autorizados" "HTTP/JSON"
        sistema.graphqlGateway -> sistema.payments "Agrega cobros y devoluciones autorizados" "HTTP/JSON"
    }

        // ========================================
        // 11. VISTAS DE ARQUITECTURA
        // ========================================

    views {
        systemContext sistema "C1_Contexto" "Contexto de negocio: actores y dependencias externas." {
            title "C1 - Contexto de Fit Express"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores" "Aplicaciones y almacenes de datos de Fit Express." {
            title "C2 - Contenedores de Fit Express"
            include *
            autoLayout lr
        }

        container sistema "C2_Catalogo" "Recorrido estructural relacionado con el catálogo." {
            title "C2 - Vista de Catálogo"
            include visitante cliente sistema.frontend sistema.apiGateway sistema.authService sistema.graphqlGateway sistema.inventory sistema.dbInventory
            autoLayout lr
        }

        container sistema "C2_Pedidos" "Recorrido estructural relacionado con el registro y gestión de pedidos." {
            title "C2 - Vista de Pedidos"
            include cliente operador sistema.frontend sistema.apiGateway sistema.authService sistema.graphqlGateway sistema.orders sistema.inventory sistema.clients sistema.payments sistema.dbOrders proveedor
            autoLayout lr
        }

        component sistema.apiGateway "C3_API_Gateway" "Componentes internos del punto de entrada HTTP." {
            title "C3 - API Gateway"
            include *
            autoLayout lr
        }

        component sistema.graphqlGateway "C3_GraphQL" "Validación, autorización y agregación de datos." {
            title "C3 - GraphQL Gateway"
            include *
            autoLayout lr
        }

        component sistema.authService "C3_Auth_Service" "Identidad, sesiones, credenciales y secretos." {
            title "C3 - Auth Service"
            include *
            autoLayout lr
        }

        component sistema.orders "C3_Orders" "Autorización, idempotencia, lógica y persistencia de pedidos." {
            title "C3 - Orders"
            include *
            autoLayout lr
        }

        // ========================================
        // 12. ESTILOS MINIMALISTAS
        // ========================================

        styles {
            element "Person" {
                shape person
                background #56718A
                color #FFFFFF
            }

            element "Software System" {
                shape roundedbox
                background #0C527A
                color #FFFFFF
            }

            element "Container" {
                shape roundedbox
                background #D5E8EF
                color #173B5D
            }

            element "Frontend" {
                shape webbrowser
                background #CDE5F7
                color #153E5B
            }

            element "Gateway" {
                background #2B6289
                color #FFFFFF
            }

            element "Seguridad" {
                background #3F6171
                color #FFFFFF
            }

            element "Privado" {
                background #D5E8EF
                color #173B5D
            }

            element "BaseDatos" {
                shape cylinder
                background #E5EAF0
                color #243F56
            }

            element "SistemaExterno" {
                background #F1EDE7
                color #544633
                stroke #A89D8A
            }

            element "Analitica" {
                background #E7E0F2
                color #453166
            }

            relationship "Relationship" {
                color #60758A
                thickness 2
            }

            element "Component" {
                shape roundedbox
                background #EDF3F7
                color #173B5D
            }

            element "EntradaC3" {
                background #D3E9F7
                color #153F62
            }

            element "ControlC3" {
                background #DBE4EC
                color #213F56
            }

            element "AplicacionC3" {
                background #D7E9DE
                color #20533E
            }

        }
    }
}
