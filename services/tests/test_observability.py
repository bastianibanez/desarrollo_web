"""La frontera HTTP registra plantillas, nunca tokens, cuerpos ni query strings."""

import logging

import pytest


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
    assert "route=/simulador/pagos/checkout/{token}" in caplog.text
    assert "request_id=correlacion-prueba" in caplog.text
    for sensitive in ("token-confidencial", "privado@example.com", "Bearer secreto"):
        assert sensitive not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("length", ["invalid", "-1"])
async def test_invalid_content_length_is_client_error(stack, length):
    response = await stack.http.post(
        "/api/login", headers={"Content-Length": length}, content=b"{}"
    )
    assert response.status_code == 400
    assert response.json()["codigo"] == "HTTP_400"
