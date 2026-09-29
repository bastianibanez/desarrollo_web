"""Crea un usuario administrador desde la terminal.

Uso, dentro del contenedor del backend:
    docker compose exec backend_api python crear_admin.py [usuario]

Pide la contraseña sin mostrarla; no se guarda en ningún archivo.
"""

import getpass
import sys

import db
from seguridad import hash_password


def crear_admin(conn, identificador: str, password: str) -> None:
    identificador = identificador.strip().lower()
    if not identificador:
        raise ValueError("El usuario no puede estar vacío")
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if conn.execute(
        "SELECT 1 FROM usuarios WHERE identificador = ?", (identificador,)
    ).fetchone():
        raise ValueError("Ya existe un usuario con ese nombre")
    with conn:
        conn.execute(
            "INSERT INTO usuarios (identificador, password_hash, rol) VALUES (?, ?, 'administrador')",
            (identificador, hash_password(password)),
        )


def main() -> int:
    identificador = sys.argv[1] if len(sys.argv) > 1 else input("Usuario: ")
    password = getpass.getpass("Contraseña: ")
    if password != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden", file=sys.stderr)
        return 1

    db.inicializar()
    conn = db.conectar()
    try:
        crear_admin(conn, identificador, password)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Administrador '{identificador.strip().lower()}' creado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
