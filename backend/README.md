# Backend FitExpress (FastAPI)

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # solo ejecución: requirements.txt
```

## Ejecución

```bash
fastapi dev main.py --port 3000
```

Se usa el puerto 3000, el mismo del servidor Express anterior. La base SQLite se
crea y se siembra sola al arrancar en `tienda.db`; para usar otra ruta, definir
`TIENDA_DB`.

Documentación interactiva: http://localhost:3000/docs

## Tests

```bash
pytest
```

## Formato de errores

Todos los errores responden con la clave `detail` (convención de FastAPI; el
servidor Express usaba `error`).

| Código | Cuándo | `detail` |
|---|---|---|
| 400 | Regla de negocio: comuna sin despacho, producto, combo o categoría inexistente | texto, p. ej. `"Producto no existe"` |
| 404 | Recurso no encontrado | `"No encontrado"` |
| 409 | Violación de integridad en la base, p. ej. borrar un producto que está en un combo | `"Conflicto con datos existentes"` |
| 422 | Body inválido (validación Pydantic; Express respondía 400) | lista de errores con `loc`, `msg` y `type` |

Ejemplo de 422:

```json
{
  "detail": [
    {"type": "missing", "loc": ["body", "nombre"], "msg": "Field required", "input": {}}
  ]
}
```
