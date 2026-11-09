"""La demo estática se inicia sin autenticación ni solicitudes al backend."""

import shutil
import subprocess
from pathlib import Path


def test_frontend_demo_without_backend(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for name in ("api.js", "demo.js", "demo-datos.js"):
        shutil.copyfile(root / "frontend" / "src" / name, tmp_path / name)
    (tmp_path / "package.json").write_text('{"type":"module"}')
    script = r"""
import assert from 'node:assert/strict';
globalThis.fetch = () => { throw new Error('La demo no debe llamar al backend'); };
globalThis.sessionStorage = new Proxy({}, {get() { throw new Error('No requiere tokens'); }});
globalThis.location = {pathname: '/cuenta.html'};
const api = await import('./api.js');
assert.equal((await api.yo()).rol, 'cliente');
assert.ok((await api.yo()).perfil.nombres);
const products = await api.getProductos();
assert.ok(products.length > 0);
products[0].nombre = 'Cambio externo';
assert.notEqual((await api.getProductos())[0].nombre, 'Cambio externo');
assert.ok((await api.getCombos()).length);
assert.ok((await api.getComunas()).length);
assert.ok((await api.getPedidos('cliente')).length);
const report = await api.getReporte('2026-11-01', '2026-11-30');
assert.equal(report.total, report.ventas.reduce((n, v) => n + v.total, 0));
assert.equal((await api.getReporte('2030-01-01', '2030-01-31')).ventas.length, 0);
await assert.rejects(api.crearOrden({}), /Demo estática/);
await assert.rejects(api.iniciarPago(1003), /Demo estática/);
await assert.rejects(api.login({}), /Demo estática/);
assert.equal((await api.getPedido(1003)).estado, 'pagado');
globalThis.location.pathname = '/panel.html';
assert.equal((await api.yo()).rol, 'administrador');
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
