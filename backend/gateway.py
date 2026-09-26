from fastapi.responses import JSONResponse
from fastapi import FastAPI
import httpx
from modelos import ProductoIn, OrdenIn

app = FastAPI(title="Local Api Gateway")

BACKEND_URL = "http://localhost:9000"


@app.get("/categorias")
async def listar_categorias():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/categorias")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/productos")
async def listar_productos():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/productos")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/productos/{id}")
async def obtener_producto(id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/productos/{id}")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.post("/productos", status_code=201)
async def crear_producto(datos: ProductoIn):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/productos", json=datos.model_dump()
        )

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.put("/productos/{id}")
async def actualizar_producto(id: int, datos: ProductoIn):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BACKEND_URL}/productos/{id}", json=datos.model_dump()
        )

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.delete("/productos/{id}")
async def eliminar_producto(id: int):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BACKEND_URL}/productos/{id}")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/combos")
async def listar_combos():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/combos")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/comunas")
async def listar_comunas():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/comunas")

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.post("/ordenes", status_code=201)
async def crear_orden(datos: OrdenIn):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BACKEND_URL}/ordenes", json=datos.model_dump())

    return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/ordenes/{id}")
async def obtener_orden(id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/ordenes/{id}")

    return JSONResponse(status_code=response.status_code, content=response.json())
