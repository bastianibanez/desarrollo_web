"""El front habla con el gateway: Bearer, X-Request-ID, errores tipados y guardia de sesión."""

import shutil
import subprocess
from pathlib import Path

PRELUDIO = r"""
import assert from 'node:assert/strict';
const store = new Map();
globalThis.sessionStorage = { getItem: k => store.get(k) ?? null,
  setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
let destino = null;
globalThis.location = { pathname: '/panel.html', search: '', replace: url => { destino = url; } };
const calls = [];
let next;
globalThis.fetch = async (url, opts) => { calls.push({ url, opts }); return next(); };
const json = (status, body, headers = {}) => new Response(JSON.stringify(body),
  { status, headers: { 'Content-Type': 'application/json', ...headers } });
// requerirSesion nunca resuelve cuando redirige: se espera un instante y se mira el destino.
const pendiente = p => Promise.race([p, new Promise(r => setTimeout(() => r('pendiente'), 50))]);
"""

API = r"""
const api = await import('./api.js');

next = () => json(200, { access_token: 't1', token_type: 'bearer', expires_in: 60 });
await api.login({ username: 'a@example.com', password: 'clave' });
assert.equal(calls[0].url, 'http://localhost:8000/api/login');
assert.equal(calls[0].opts.method, 'POST');
assert.ok(calls[0].opts.headers['X-Request-ID']);
assert.equal(calls[0].opts.headers.Authorization, undefined);

store.set(api.TOKEN_KEY, 't1');
next = () => json(401, { detail: 'Token inválido o expirado', codigo: 'HTTP_401' }, { 'X-Request-ID': 'R9' });
await assert.rejects(api.logout(), e => e.status === 401 && e.requestId === 'R9'
  && e.message === 'Token inválido o expirado');
assert.equal(calls[1].opts.headers.Authorization, 'Bearer t1');
assert.equal(store.has(api.TOKEN_KEY), false);

next = () => json(429, { detail: 'Límite de solicitudes excedido', codigo: 'HTTP_429' }, { 'Retry-After': '60' });
await assert.rejects(api.login({}), e => e.status === 429 && e.retryAfter === 60);

next = () => { throw new TypeError('Failed to fetch'); };
await assert.rejects(api.login({}), e => e.status === 0 && e.codigo === 'RED' && Boolean(e.requestId));

store.set(api.TOKEN_KEY, 't2');
next = () => json(200, { data: { perfil: { id: '5', identificador: 'c@example.com', rol: 'cliente',
  datosCliente: { nombres: 'Ana', apellidos: 'Soto' } } } });
const perfil = await api.obtenerPerfil();
assert.equal(perfil.rol, 'cliente');
assert.equal(perfil.perfil.nombres, 'Ana');
assert.equal(calls.at(-1).url, 'http://localhost:8000/api/graphql');

next = () => json(200, { errors: [{ message: 'Sesión requerida', extensions: { code: 'UNAUTHENTICATED' } }] });
await assert.rejects(api.obtenerPerfil(), e => e.status === 401 && e.codigo === 'UNAUTHENTICATED');
assert.equal(store.has(api.TOKEN_KEY), false);

// El resto de la demo sigue sin red.
const antes = calls.length;
assert.ok((await api.getProductos()).length > 0);
await assert.rejects(api.crearOrden({}), /Demo estática/);
assert.equal(calls.length, antes);
"""

GUARDIA = r"""
const s = await import('./sesion.js');
const perfil = rol => () => json(200, { data: { perfil: { id: '1', rol, datosCliente: null } } });

assert.equal(await pendiente(s.requerirSesion(['administrador'])), 'pendiente');
assert.equal(destino, 'acceso.html?motivo=sin-sesion&volver=panel.html');
assert.equal(calls.length, 0);

store.set('access_token', 'vencido');
next = () => json(401, { detail: 'Token inválido o expirado', codigo: 'HTTP_401' });
assert.equal(await pendiente(s.requerirSesion(['administrador'])), 'pendiente');
assert.equal(destino, 'acceso.html?motivo=expirada&volver=panel.html');
assert.equal(store.has('access_token'), false);

store.set('access_token', 't');
next = perfil('cliente');
assert.equal(await pendiente(s.requerirSesion(['administrador'])), 'pendiente');
assert.equal(destino, 'cuenta.html?motivo=sin-permiso');

next = perfil('administrador');
assert.equal((await s.requerirSesion(['administrador'])).rol, 'administrador');

next = () => json(503, { detail: 'Servicio no disponible', codigo: 'HTTP_503' });
await assert.rejects(s.requerirSesion(['administrador']), e => e.status === 503);
assert.equal(store.get('access_token'), 't');

next = () => json(200, { message: 'Sesión finalizada' });
await s.cerrarSesion();
assert.equal(destino, 'acceso.html?motivo=cerrada');
assert.equal(store.has('access_token'), false);
"""


def run_node(tmp_path, script):
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    for name in ("api.js", "sesion.js", "demo.js", "demo-datos.js"):
        shutil.copyfile(src / name, tmp_path / name)
    (tmp_path / "package.json").write_text('{"type":"module"}')
    result = subprocess.run(
        ["node", "--input-type=module", "-e", PRELUDIO + script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_api_habla_con_gateway(tmp_path):
    run_node(tmp_path, API)


def test_guardia_de_sesion(tmp_path):
    run_node(tmp_path, GUARDIA)
