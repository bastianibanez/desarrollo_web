"""Autenticación conectada: límites, expiración, dependencias caídas o lentas, CORS y Vault."""

import json

import httpx
import pytest

from services.auth.auth_service import create_app as auth_app
from services.auth.auth_service import session_ttl
from services.bootstrap import verify
from services.common import Context
from services.manage import expire_sessions

pytestmark = pytest.mark.asyncio

PERFIL = {"query": "{ perfil { identificador rol } }"}


async def login(stack, username="cliente@example.com", password="Clave-de-prueba-123"):
    return await stack.http.post(
        "/api/login", json={"username": username, "password": password}
    )


async def test_login_limit_is_per_user(stack):
    for _ in range(5):
        assert (await login(stack, "a@example.com", "mala")).status_code == 401
    blocked = await login(stack, "a@example.com", "mala")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    other = await login(stack)
    assert other.status_code == 200, other.text
    assert other.json()["expires_in"] == 28800


async def test_session_ttl_comes_from_environment(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_TTL_SECONDS", "600")
    assert session_ttl() == 600
    for invalid in ("30", "999999", "-1", "diez"):
        monkeypatch.setenv("AUTH_SESSION_TTL_SECONDS", invalid)
        with pytest.raises(RuntimeError):
            session_ttl()


async def test_expired_session_is_rejected_without_touching_others(stack):
    cliente = stack.users["cliente"]
    assert expire_sessions(stack.ctx["auth"], cliente["id"]) == 1
    expired = await stack.http.post(
        "/api/graphql", headers=stack.headers("cliente"), json=PERFIL
    )
    assert expired.status_code == 401
    assert expired.json()["detail"] == "Token inválido o expirado"
    alive = await stack.http.post(
        "/api/graphql", headers=stack.headers("administrador"), json=PERFIL
    )
    assert alive.json()["data"]["perfil"]["rol"] == "administrador"


@pytest.mark.parametrize(
    ("failure", "status", "codigo"),
    [("slow", 504, "DEPENDENCY_TIMEOUT"), ("offline", 503, "DEPENDENCY_UNAVAILABLE")],
)
@pytest.mark.parametrize("service", ["auth", "clients"])
async def test_auth_dependency_failure_is_controlled_and_recovers(
    stack, failure, status, codigo, service
):
    getattr(stack.router, failure).add(service)
    for response in (
        await login(stack),
        await stack.http.post(
            "/api/graphql", headers=stack.headers("cliente"), json=PERFIL
        ),
    ):
        assert response.status_code == status, response.text
        assert response.json()["codigo"] == codigo
        assert response.headers["x-request-id"]
    getattr(stack.router, failure).clear()
    assert (await login(stack)).status_code == 200
    recovered = await stack.http.post(
        "/api/graphql", headers=stack.headers("cliente"), json=PERFIL
    )
    assert recovered.json()["data"]["perfil"]["rol"] == "cliente"


async def test_cors_allows_front_origin_even_on_errors(stack):
    front = {"Origin": "http://localhost:5173"}
    preflight = await stack.http.options(
        "/api/login",
        headers={**front, "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == front["Origin"]
    foreign = await stack.http.options(
        "/api/login",
        headers={
            "Origin": "http://otro.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in foreign.headers
    denied = await stack.http.post("/api/logout", headers=front)
    assert denied.status_code == 401
    assert denied.headers["access-control-allow-origin"] == front["Origin"]
    assert "X-Request-ID" in denied.headers["access-control-expose-headers"]


async def test_vault_unavailable_rejects_without_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_TOKEN_FILE", str(tmp_path / "sin-token"))
    app = auth_app(Context("auth", tmp_path))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://auth"
    ) as http:
        response = await http.post("/login", json={"username": "a", "password": "b"})
    assert response.status_code == 503
    assert response.json()["codigo"] == "VAULT_UNAVAILABLE"


def vault(tokens, leak=False):
    def handle(request):
        token = request.headers["x-vault-token"]
        path = request.url.path
        if path == "/v1/auth/token/lookup":
            owner = tokens[json.loads(request.content)["token"]]
            return httpx.Response(
                200,
                json={
                    "data": {
                        "policies": [f"fit-{owner}"],
                        "ttl": 3600,
                        "renewable": False,
                    }
                },
            )
        own = path == f"/v1/secret/data/services/{tokens.get(token)}"
        return httpx.Response(200 if own or (leak and "secret" in path) else 403)

    return httpx.MockTransport(handle)


async def test_verify_vault_reports_least_privilege_without_values(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("VAULT_TOKEN", "raiz")
    tokens = {"token-auth": "auth", "token-gateway": "gateway"}
    for value, name in tokens.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "token").write_text(value)
    assert verify(tmp_path, vault(tokens)) == 0
    report = capsys.readouterr().out
    assert report.count("OK") == 2
    assert "token-" not in report and "raiz" not in report
    assert verify(tmp_path, vault(tokens, leak=True)) == 2
    assert "FALLA" in capsys.readouterr().out
