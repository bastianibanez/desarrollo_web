import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException

import db


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def password_valida(password: str, guardada: str | None) -> bool:
    if not guardada:
        return False
    salt_hex, digest_hex = guardada.split(":", 1)
    calculado = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
    )
    return hmac.compare_digest(calculado, bytes.fromhex((digest_hex)))


def crear_sesion(conn, usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expira = datetime.now(timezone.utc) + timedelta(hours=8)
    with conn:
        conn.execute(
            "INSERT INTO sesiones VALUES (?,?,?)",
            (token_hash, usuario_id, expira.isoformat()),
        )


def usuario_actual(x_user_session: str = Header(default=""), conn=Depends(db.get_db)):
    token_hash = hashlib.sha256(x_user_session.encode()).hexdigest()
    fila = conn.execute(
        """
        SELECT u.*, c.email_verificado_at FROM sesiones s
        JOIN usuarios u ON u.id = s.usuario_id
        LEFT JOIN clientes c ON c.id = u.cliente_id
        WHERE s.token_hash = ? AND u.activo = 1 AND s.expira_at > ?
    """,
        (token_hash, datetime.now(timezone.utc).isoformat()),
    ).fetchone()

    if fila is None:
        raise HTTPException(401, "Sesion requerida o vencida")
    return dict(fila)


def requiere(*roles: str):
    def comprobar(usuario=Depends(usuario_actual)):
        if usuario["rol"] not in roles:
            raise HTTPException(403, "Perfil sin permiso")
        return usuario

    return comprobar
