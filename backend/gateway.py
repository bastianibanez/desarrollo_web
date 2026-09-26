from fastapi import FastAPI
import httpx
from modelos import ProductoIn, ClienteIn, DireccionIn, ItemIn, OrdenIn

app = FastAPI(title="Local Api Gateway")

BACKEND_URL = "http://localhost:9000"


@app.get("/categorias")
async def products():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/categorias")

    return response.json()


@app.get("/productos")
async def listar_productos():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/productos")

    return response.json()


@app.get("/productos/{id}")
async def obtener_producto(id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/productos/{id}")

    return response.json()


@app.post("/productos", status_code=201)
def crear_producto():
    pass
