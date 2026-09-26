from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import httpx
import os
from modelos import ProductoIn, OrdenIn

app = FastAPI(title="Local Api Gateway")

security = HTTPBearer(auto_error=False)

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")

VAULT_TOKEN = os.getenv("VAULT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://192.168.1.20:9000")
if not VAULT_TOKEN:
    raise RuntimeError("VAULT_TOKEN no configurado")


async def get_gateway_secrets():
    url = f"{VAULT_ADDR}/v1/secret/data/gateway"
    headers = {"X-Vault-Token": VAULT_TOKEN}

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="No fue posible acceder a Vault")

    vault_response = response.json()
    return vault_response["data"]["data"]


async def authenticate_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token requerido")
    vault_secrets = await get_gateway_secrets()
    expected_token = vault_secrets["client_token"]
    received_token = credentials.credentials

    valid = secrets.compare_digest(received_token, expected_token)

    if not valid:
        raise HTTPException(status_code=401, detail="Token invalido")

    return {
        "client_id": "student-client",
        "backend_secret": vault_secrets["backend_shared_secret"],
    }


@app.get("/health")
def health():
    return {"status": "OK", "service": "API Gateway"}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request, auth=Depends(authenticate_client)):
    target_url = f"{BACKEND_URL}/{path}"

    body = await request.body()

    gateway_headers = {
        "X-Gateway-Secret": auth["backend_secret"],
        "X-Authenticated-Client": auth["client_id"],
    }

    content_type = request.headers.get("content-type")

    if content_type:
        gateway_headers["content-type"] = content_type

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=gateway_headers,
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Backend no disponible")

    response_headers = {}

    if "content-type" in upstream.headers:
        response_headers["content-type"] = upstream.headers["content-type"]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


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
