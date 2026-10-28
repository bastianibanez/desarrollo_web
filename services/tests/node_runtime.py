"""Ejecuta el GraphQL Node real para las pruebas de integración."""

import asyncio
import json
import os
import socket
from contextlib import asynccontextmanager

import httpx


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@asynccontextmanager
async def node_server(folder, keys, urls):
    folder.mkdir(parents=True, exist_ok=True)
    identity = folder / "identity.json"
    identity.write_text(json.dumps(keys))
    identity.chmod(0o600)
    port = free_port()
    env = {
        **os.environ,
        "NODE_ENV": "test",
        "TEST_IDENTITY_FILE": str(identity),
        "PORT": str(port),
        **{name.upper() + "_URL": url for name, url in urls.items()},
    }
    process = await asyncio.create_subprocess_exec(
        "node",
        "services/graphql/server.js",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with httpx.AsyncClient() as http:
            for _ in range(100):
                if process.returncode is not None:
                    raise RuntimeError(
                        "GraphQL Node no inició: "
                        + (await process.stderr.read()).decode()
                    )
                try:
                    if (
                        await http.get(f"http://127.0.0.1:{port}/health")
                    ).status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                await asyncio.sleep(0.05)
            else:
                raise RuntimeError("GraphQL Node no respondió al healthcheck")
        yield f"http://127.0.0.1:{port}"
    finally:
        if process.returncode is None:
            process.terminate()
        await asyncio.wait_for(process.communicate(), 10)
