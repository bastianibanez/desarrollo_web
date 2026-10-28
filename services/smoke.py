"""Demostración contra el backend desplegado; requiere seed-demo explícito previo."""

import argparse
import getpass
import json
import secrets
import sys

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    password = (
        sys.stdin.readline().rstrip("\n")
        if args.password_stdin
        else getpass.getpass("Contraseña de las cuentas seed-demo: ")
    )
    with httpx.Client(base_url=args.url, timeout=20) as http:

        def request(method, path, role=None, body=None):
            headers = {"Idempotency-Key": secrets.token_hex(16)}
            if role:
                headers["Authorization"] = "Bearer " + tokens[role]
            response = http.request(method, path, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                raise RuntimeError(
                    "GraphQL rechazó la demostración; revisar permisos/servicios"
                )
            return result

        tokens, ids = {}, {}
        for role in ("administrador", "cajero", "despacho", "cliente"):
            data = request(
                "POST",
                "/api/login",
                body={"username": f"{role}@fitexpress.test", "password": password},
            )
            tokens[role] = data["access_token"]
            profile = request("POST", "/api/graphql", role, {"query": "{perfil{id}}"})
            ids[role] = int(profile["data"]["perfil"]["id"])
        request("PATCH", "/api/cajas/1", "administrador", {"cajero_id": ids["cajero"]})
        catalog = request(
            "POST",
            "/api/graphql",
            body={
                "query": "{catalogo(filtros:{productos:{soloDisponibles:true}}){productos{items{id nombre}}}}"
            },
        )
        items = catalog["data"]["catalogo"]["productos"]["items"]
        if not items:
            raise RuntimeError("Sin productos disponibles para la demostración")
        order = request(
            "POST",
            "/api/ordenes",
            "cliente",
            {
                "direccion": {
                    "calle": "Calle ficticia",
                    "numero": "10",
                    "comuna_id": 1,
                },
                "items": [{"producto_id": int(items[0]["id"]), "cantidad": 1}],
            },
        )
        payment = request("POST", "/api/pagos", "cliente", {"orden_id": order["id"]})
        outcome = request(
            "POST", payment["checkout_url"] + "/resultado", body={"estado": "aprobado"}
        )
        if not outcome["aviso_entregado"]:
            raise RuntimeError(
                "Aviso de pago pendiente; repetir el resultado del simulador"
            )
        detail = request(
            "POST",
            "/api/graphql",
            "cliente",
            {
                "query": "query($id:ID!){pedido(id:$id){id estado total comprobante{numero estadoEnvio} pago{estado}}}",
                "variables": {"id": order["id"]},
            },
        )["data"]["pedido"]
        if detail["estado"] != "pagado":
            raise RuntimeError("El aviso no dejó el pedido pagado")
        for route in ("preparacion", "envios", "entregas"):
            final = request(
                "POST", f"/api/ordenes/{order['id']}/{route}", "despacho", {}
            )
        print(
            json.dumps(
                {
                    "pedido_id": order["id"],
                    "estado": final["estado"],
                    "pago": detail["pago"]["estado"],
                    "comprobante": detail["comprobante"],
                    "frontend": "no utilizado",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
