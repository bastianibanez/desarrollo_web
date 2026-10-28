"""Provisiona identidades mínimas de Vault; no imprime ni versiona secretos."""

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


def provision():
    token = os.environ["VAULT_TOKEN"]
    address = os.getenv("VAULT_ADDR", "http://vault:8200")
    with httpx.Client(
        base_url=address, headers={"X-Vault-Token": token}, timeout=5
    ) as client:
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


if __name__ == "__main__":
    provision()
