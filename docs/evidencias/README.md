# Evidencias de la entrega

Ejecución del 9 de noviembre de 2026, sobre el código de `068f0a3` más el ensayo de carga recuperado. [resultado.json](backend-e2/resultado.json) registra comandos y hashes SHA-256 de las fuentes para poder identificar el código incluso después de depurar el historial Git.

| Comprobación | Resultado | Archivo |
| --- | --- | --- |
| Suite de servicios y demo | 38 aprobadas, 0 fallos, 0 errores | [JUnit](backend-e2/pytest.xml) |
| Carga local | 60 solicitudes, concurrencia 4, cero errores; objetivos aprobados | [Carga](backend-e2/carga-local.json) |

La suite incluye autorización, reglas de negocio, errores controlados, recorrido por HTTP real y la independencia del frontend estático. No demuestra integración visual con backend, pruebas responsivas, reinicio de Docker ni una nueva comprobación de ACL de Vault. La carga mide ASGI y Apollo por HTTP en un escenario pequeño; no representa capacidad sostenida en producción.

Reproducción desde la raíz, con las dependencias del README instaladas:

```sh
.venv/bin/python -m pytest -c services/pytest.ini services/tests --junitxml=docs/evidencias/backend-e2/pytest.xml
.venv/bin/python -m pytest -c services/pytest.ini services/benchmarks -s
```

Estos comandos reemplazan los resultados medidos. Si cambia el código, también deben actualizarse los hashes del manifiesto; no reutilizar cifras de una ejecución anterior como si fueran actuales.
