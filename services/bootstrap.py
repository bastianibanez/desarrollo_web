"""Provisiona y verifica identidades mínimas de Vault; no imprime ni versiona secretos."""

import argparse
import os
import secrets
from pathlib import Path

import httpx

EDGES = {
    "gateway": {
        "auth",
        "clients",
        "inventory",
        "orders",
        "payments",
        "graphql",
        "simulator",
    },
    "auth": {"clients"},
    "clients": {"orders"},
    "inventory": set(),
    "orders": {"clients", "inventory", "payments", "orders"},
    "payments": {"orders", "simulator"},
    "graphql": {"clients", "inventory", "orders", "payments"},
    "simulator": {"payments"},
}


def vault_client(token, transport=None):
    return httpx.Client(
        base_url=os.getenv("VAULT_ADDR", "http://vault:8200"),
        headers={"X-Vault-Token": token},
        timeout=5,
        transport=transport,
    )


def provision():
    with vault_client(os.environ["VAULT_TOKEN"]) as client:
        # Compose ya espera el healthcheck de Vault antes de iniciar este comando.
        client.get("/v1/sys/health").raise_for_status()
        identities = {}
        for name in EDGES:
            old = client.get(f"/v1/secret/data/services/{name}")
            if old.status_code == 200:
                identities[name] = old.json()["data"]["data"]
            else:
                identities[name] = {"incoming": {}, "outgoing": {}}
        for source, destinations in EDGES.items():
            for destination in destinations:
                value = identities[source]["outgoing"].get(
                    destination
                ) or secrets.token_urlsafe(48)
                identities[source]["outgoing"][destination] = value
                identities[destination]["incoming"][source] = value
        provider_key = identities["payments"].get(
            "provider_hmac"
        ) or secrets.token_urlsafe(48)
        identities["payments"]["provider_hmac"] = identities["simulator"][
            "provider_hmac"
        ] = provider_key
        for name, values in identities.items():
            response = client.post(
                f"/v1/secret/data/services/{name}", json={"data": values}
            )
            response.raise_for_status()
            policy = f'path "secret/data/services/{name}" {{ capabilities = ["read"] }}'
            client.put(
                f"/v1/sys/policies/acl/fit-{name}", json={"policy": policy}
            ).raise_for_status()
            created = client.post(
                "/v1/auth/token/create",
                json={
                    "policies": [f"fit-{name}"],
                    "no_default_policy": True,
                    "ttl": "24h",
                    "renewable": False,
                },
            )
            created.raise_for_status()
            target = Path("/identities") / name / "token"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(created.json()["auth"]["client_token"])
            target.chmod(0o600)
    print("Identidades de servicio provisionadas en Vault (sin valores en logs).")


def verify(root=Path("/identities"), transport=None):
    names = sorted(p.name for p in root.iterdir() if (p / "token").exists())
    failures = 0
    print(
        f"{'servicio':<10} {'politica':<15} {'ttl_s':>6} {'renovable':<9} "
        f"{'propio':>6} {'ajeno':>5} {'self':>4}  resultado"
    )
    with vault_client(os.environ["VAULT_TOKEN"], transport) as admin:
        for name in names:
            token = (root / name / "token").read_text().strip()
            info = admin.post("/v1/auth/token/lookup", json={"token": token})
            info.raise_for_status()
            data = info.json()["data"]
            other = next(n for n in names if n != name)
            with vault_client(token, transport) as own:
                propio = own.get(f"/v1/secret/data/services/{name}").status_code
                ajeno = own.get(f"/v1/secret/data/services/{other}").status_code
                self_lookup = own.get("/v1/auth/token/lookup-self").status_code
            ok = (
                data["policies"] == [f"fit-{name}"]
                and data["ttl"] > 0
                and not data["renewable"]
                and (propio, ajeno, self_lookup) == (200, 403, 403)
            )
            failures += not ok
            print(
                f"{name:<10} {','.join(data['policies']):<15} {data['ttl']:>6} "
                f"{data['renewable']!s:<9} {propio:>6} {ajeno:>5} {self_lookup:>4}  "
                f"{'OK' if ok else 'FALLA'}"
            )
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        default="provisionar",
        choices=["provisionar", "verificar"],
    )
    if parser.parse_args().command == "verificar":
        raise SystemExit(1 if verify() else 0)
    provision()


if __name__ == "__main__":
    main()
