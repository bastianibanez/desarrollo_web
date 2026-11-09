# ADR 001 · REST privado y reportes sin servicio analítico adicional

Estado: aceptado para el alcance académico local. Reconsiderar al cambiar carga o requisitos.

## Contexto y alternativas

Fit Express procesa compras discretas y consulta reportes por período. No hay requisito de telemetría continua, audio/video, procesamiento masivo ni streaming bidireccional. La proyección de demostración es cuatro lectores concurrentes, páginas de hasta 50 elementos y cinco pedidos pagados para el escenario reproducible. Esto no representa demanda comercial medida.

Alternativas: (1) REST privado + GraphQL de agregación y consultas SQL en el servicio dueño; (2) servicio analítico con copia de datos y actualización asíncrona; (3) contratos gRPC internos. La primera mantiene el patrón HTTP del profesor y permite consultar ventas de orders y movimientos de payments sin compartir bases. Las otras introducen replicación, desfase o una segunda pila de contratos sin un requisito que lo demande.

## Decisión

No implementar gRPC ni otro servicio analítico para este volumen. Orders calcula ventas; payments calcula cobros y devoluciones; G06 los combina. No se sostiene que HTTP sea más rápido que gRPC: no se ha comparado. La consulta es unary conceptual y acotada por páginas; no necesita streaming. Las mutaciones permanecen en servicios transaccionales.

| Necesidad | Solución / umbral para reconsiderar |
| --- | --- |
| Reporte por fecha sin datos personales innecesarios | SQL y agregación GraphQL; separar analítica si bloquea compras o se requieren agregaciones masivas |
| Lecturas concurrentes | Objetivo del experimento: p95 < 1 s, al menos 5 solicitudes/s, cero errores |
| Tamaño de respuesta | Medido en JSON de evidencia; paginación máxima 50 y costo GraphQL máximo 2000 |
| Streaming | No requerido; evaluar gRPC si aparecen consumidores internos de eventos continuos |
| Consistencia financiera | Fuente oficial por sistema; reportes no son una instantánea atómica distribuida |

## Medición reproducible

Desde la raíz, con las dependencias del README instaladas:

```sh
.venv/bin/python -m pytest -c services/pytest.ini services/benchmarks -s
```

El script crea cinco compras pagadas con APIs reales y bases temporales, precalienta catálogo/reporte y mide 60 solicitudes (40 catálogo, 20 reporte) con concurrencia cuatro. Respeta los límites de usuario/IP del gateway, no los desactiva. Comprueba HTTP y errores GraphQL. Guarda entorno, duración, p95 por rango más próximo, throughput, bytes, errores, CPU Python y memoria máxima en [carga-local.json](evidencias/backend-e2/carga-local.json).

Limitaciones: Apollo es un proceso Node real conectado por sockets; el gateway y los servicios Python usan transporte ASGI y un puente HTTP. No mide latencia de Docker/Vault ni capacidad sostenida, y CPU/RSS cubren solo Python (RSS máximo del proceso, no delta de ventana). La prueba HTTP completa separada verifica la conectividad, no constituye una carga. La decisión queda respaldada para esta demostración pequeña; no extrapolar a producción ni declarar medido el consumo de todos los contenedores.

Consecuencias: menos infraestructura y un único protocolo privado. Los reportes compiten por SQLite con las transacciones; ampliar datos y duración del ensayo antes de elevar los objetivos. Si falla el umbral o la carga real crece, medir el despliegue completo y evaluar índices/consultas antes de separar analítica o cambiar el transporte.
