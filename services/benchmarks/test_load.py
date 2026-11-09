"""Carga académica reproducible: pytest services/benchmarks -s (no es producción)."""

import asyncio
import json
import math
import platform
import resource
import time
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_projected_read_load(stack):
    # Datos reales creados mediante los contratos, fuera de la ventana medida.
    for _ in range(5):
        order = await stack.checkout()
        await stack.pay(order)
    catalog = (
        "{catalogo(limite:12){productos{items{id nombre precioFinal disponible}}}}"
    )
    report = 'query{reporteVentas(desde:"2020-01-01",hasta:"2030-12-31"){cantidadVentas totalCobrado totalDevuelto netoCobrado ventas{items{id total}}}}'
    for query, role in ((catalog, None), (report, "dueno")):
        warmup = await stack.query(query, role=role)
        assert "errors" not in warmup.json()
    samples, sizes, errors = [], [], []
    semaphore = asyncio.Semaphore(4)
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()

    async def request(index):
        async with semaphore:
            start = time.perf_counter()
            response = await stack.query(
                report if index % 3 == 0 else catalog,
                role="dueno" if index % 3 == 0 else None,
            )
            samples.append((time.perf_counter() - start) * 1000)
            sizes.append(len(response.content))
            if response.status_code != 200 or response.json().get("errors"):
                errors.append({"status": response.status_code, "body": response.json()})

    await asyncio.gather(*(request(i) for i in range(60)))
    duration = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_SELF)
    p95 = sorted(samples)[math.ceil(len(samples) * 0.95) - 1]
    result = {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "transport": "Gateway y APIs ASGI; Apollo Node real por HTTP y puente HTTP a APIs; sin Docker/Vault",
        "dataset": {"paid_orders": 5, "catalog_page_size": 12},
        "requests": 60,
        "concurrency": 4,
        "catalog_requests": 40,
        "report_requests": 20,
        "duration_seconds": duration,
        "p95_ms": p95,
        "throughput_rps": 60 / duration,
        "response_bytes_mean": sum(sizes) / len(sizes),
        "errors": errors,
        "python_cpu_seconds": after.ru_utime
        + after.ru_stime
        - before.ru_utime
        - before.ru_stime,
        "python_peak_rss_bytes": after.ru_maxrss
        * (1 if platform.system() == "Darwin" else 1024),
        "resource_scope": "Proceso Python: CPU de ventana y RSS máximo desde inicio; excluye Node. No equivale al consumo del despliegue.",
        "targets": {"p95_ms_max": 1000, "throughput_rps_min": 5, "errors_max": 0},
        "passed": not errors and p95 < 1000 and 60 / duration >= 5,
    }
    output = Path("docs/evidencias/backend-e2/carga-local.json")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    assert result["passed"], result
