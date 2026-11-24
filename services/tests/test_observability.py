"""La frontera HTTP registra plantillas, nunca tokens, cuerpos ni query strings."""

import logging

import httpx
import pytest


def linea(caplog, *fragmentos):
    for i, mensaje in enumerate(caplog.messages):
        if all(f in mensaje for f in fragmentos):
            return i
    raise AssertionError(f"sin línea con {fragmentos}")


@pytest.mark.asyncio
async def test_request_log_redacts_url_and_credentials(stack, caplog):
    with caplog.at_level(logging.INFO, logger="fitexpress"):
        response = await stack.http.get(
            "/simulador/pagos/checkout/token-confidencial?email=privado@example.com",
            headers={
                "X-Request-ID": "correlacion-prueba",
                "Authorization": "Bearer secreto",
            },
        )
    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "correlacion-prueba"
    assert "/simulador/pagos/checkout/{token}" in caplog.text
    assert "correlacion-prueba" not in caplog.text
    for sensitive in ("token-confidencial", "privado@example.com", "Bearer secreto"):
        assert sensitive not in caplog.text


@pytest.mark.asyncio
async def test_successful_health_checks_stay_out_of_logs(stack, caplog):
    with caplog.at_level(logging.INFO, logger="fitexpress"):
        response = await stack.http.get(
            "/health", headers={"X-Request-ID": "latido-salud"}
        )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "latido-salud"
    assert "latido-salud" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("length", ["invalid", "-1"])
async def test_invalid_content_length_is_client_error(stack, length):
    response = await stack.http.post(
        "/api/login", headers={"Content-Length": length}, content=b"{}"
    )
    assert response.status_code == 400
    assert response.json()["codigo"] == "HTTP_400"


@pytest.mark.asyncio
async def test_login_and_profile_leave_one_line_per_hop(stack, caplog):
    with caplog.at_level(logging.INFO, logger="fitexpress"):
        login = await stack.http.post(
            "/api/login",
            headers={"X-Request-ID": "R-login"},
            json={"username": "cliente@example.com", "password": "Clave-de-prueba-123"},
        )
        token = login.json()["access_token"]
        perfil = await stack.http.post(
            "/api/graphql",
            headers={"X-Request-ID": "R-perfil", "Authorization": "Bearer " + token},
            json={"query": "{ perfil { rol } }"},
        )
    assert perfil.json()["data"]["perfil"]["rol"] == "cliente"
    user_id = stack.users["cliente"]["id"]
    for secuencia in (
        (
            ("<- navegador", "POST  /api/login"),
            ("-> auth", "POST  /login"),
            ("<- gateway", "POST  /login", "secreto OK"),
            ("-> clients", "POST  /interno/auth/credenciales"),
            ("<- auth", "POST  /interno/auth/credenciales", "secreto OK"),
            (
                "-> auth",
                "POST  /interno/auth/credenciales",
                " 200 ",
                "BD SELECT usuarios",
            ),
            (
                "-> gateway",
                "POST  /login",
                " 200 ",
                f"sesión creada (usuario {user_id}) - BD INSERT sesiones",
            ),
            ("-> navegador", "POST  /api/login", " 200 "),
        ),
        (
            ("<- navegador", "POST  /api/graphql"),
            ("-> auth", "POST  /introspect"),
            ("<- gateway", "POST  /introspect", "secreto OK"),
            ("-> clients", f"GET   /interno/usuarios/{user_id}"),
            ("<- auth", "GET   /interno/usuarios/{id}", "secreto OK"),
            ("-> auth", "GET   /interno/usuarios/{id}", " 200 ", "BD SELECT usuarios"),
            (
                "-> gateway",
                "POST  /introspect",
                " 200 ",
                f"token válido (usuario {user_id}, cliente) - BD SELECT sesiones",
            ),
            ("-> graphql", "POST  /graphql"),
            (
                "-> navegador",
                "POST  /api/graphql",
                " 200 ",
                f"autorizado (usuario {user_id}, cliente)",
            ),
        ),
    ):
        posiciones = [linea(caplog, *fragmentos) for fragmentos in secuencia]
        assert posiciones == sorted(posiciones)
    assert "R-login" not in caplog.text and "R-perfil" not in caplog.text
    for sensitive in ("Clave-de-prueba-123", token, "cliente@example.com"):
        assert sensitive not in caplog.text


@pytest.mark.asyncio
async def test_denied_actions_leave_events(stack, caplog):
    with caplog.at_level(logging.INFO, logger="fitexpress"):
        forbidden = await stack.http.post(
            "/api/productos",
            headers={**stack.headers("cliente"), "X-Request-ID": "R-rol"},
            json={},
        )
        anonymous = await stack.http.post(
            "/api/logout", headers={"X-Request-ID": "R-anonimo"}
        )
    assert forbidden.status_code == 403 and anonymous.status_code == 401
    linea(
        caplog,
        "-> navegador",
        "POST  /api/productos",
        " 403 ",
        "prohibido para rol cliente",
    )
    linea(
        caplog,
        "-> navegador",
        "POST  /api/logout",
        " 401 ",
        "sin sesión válida (sin token)",
    )


@pytest.mark.asyncio
async def test_backend_rejects_calls_without_vault_secret(stack, caplog):
    clients = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=stack.router.apps["clients"]),
        base_url="http://clients",
    )
    with caplog.at_level(logging.INFO, logger="fitexpress"):
        async with clients:
            response = await clients.get(
                "/perfil",
                headers={"X-Gateway-Secret": "falso", "X-Request-ID": "R-sin-secreto"},
            )
    assert response.status_code == 403
    llegada = linea(caplog, "<- ?", "GET   /perfil", "secreto inválido")
    respuesta = linea(
        caplog, "-> ?", "GET   /perfil", " 403 ", "rechazada sin tocar la BD"
    )
    assert llegada < respuesta
    assert "BD SELECT" not in caplog.text
