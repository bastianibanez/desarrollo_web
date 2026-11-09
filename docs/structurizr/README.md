# Modelo C4

[Fuente editable](workspace.dsl), adaptada al modelo de la clase del 4 de noviembre. Complementa la matriz de sistemas del [informe](../informe-evaluacion-2.md).

Este C4 representa la arquitectura de integración prevista. Las flechas desde el frontend al gateway no describen tráfico de la demo estática actual. El backend sí mantiene las dependencias privadas representadas. Los componentes agrupan responsabilidades, no implican clases Python ni procesos adicionales.

| Vista | Exportación |
| --- | --- |
| C1_Contexto | [C1_Contexto.svg](svg/C1_Contexto.svg) |
| C2_Catalogo | [C2_Catalogo.svg](svg/C2_Catalogo.svg) |
| C2_Contenedores | [C2_Contenedores.svg](svg/C2_Contenedores.svg) |
| C2_Pedidos | [C2_Pedidos.svg](svg/C2_Pedidos.svg) |
| C3_API_Gateway | [C3_API_Gateway.svg](svg/C3_API_Gateway.svg) |
| C3_Auth_Service | [C3_Auth_Service.svg](svg/C3_Auth_Service.svg) |
| C3_GraphQL | [C3_GraphQL.svg](svg/C3_GraphQL.svg) |
| C3_Orders | [C3_Orders.svg](svg/C3_Orders.svg) |

El DSL es autónomo y puede abrirse en Structurizr. Los SVG se incluyen para lectura sin herramientas adicionales. No son evidencia de una integración del frontend ya ejecutada.
