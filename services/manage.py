"""Administración local: ejecutar dentro del contenedor clients, sin APIs públicas extra."""

import argparse
import getpass
import json
import sys

from services.common import Context, now, password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin", "seed-demo", "mensajes"])
    parser.add_argument("--identificador", default="admin@fitexpress.test")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    ctx = Context("clients")
    ctx.initialize()
    if args.command == "mensajes":
        with ctx.read() as db:
            messages = [
                dict(r)
                for r in db.execute(
                    "SELECT id,destinatario,asunto,cuerpo,estado,creado_en FROM mensajes_simulados ORDER BY creado_en DESC LIMIT 20"
                )
            ]
        print(json.dumps(messages, ensure_ascii=False))
        return
    password = (
        sys.stdin.readline().rstrip("\n")
        if args.password_stdin
        else getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    )
    if len(password) < 12:
        parser.error(
            "La contraseña de administración/demo requiere al menos 12 caracteres"
        )
    with ctx.transaction() as db:
        if args.command == "create-admin":
            db.execute(
                "INSERT INTO usuarios(identificador,password_hash,rol,created_at) VALUES(?,?,'administrador',?)",
                (args.identificador.lower(), password_hash(password), now()),
            )
            print("Administrador creado.")
        else:
            result = {}
            for role in ("administrador", "cajero", "despacho", "dueno"):
                identifier = f"{role}@fitexpress.test"
                db.execute(
                    "INSERT OR IGNORE INTO usuarios(identificador,password_hash,rol,created_at) VALUES(?,?,?,?)",
                    (identifier, password_hash(password), role, now()),
                )
                db.execute(
                    "UPDATE usuarios SET password_hash=? WHERE identificador=? AND rol=?",
                    (password_hash(password), identifier, role),
                )
                result[role] = dict(
                    db.execute(
                        "SELECT id,identificador,rol FROM usuarios WHERE identificador=?",
                        (identifier,),
                    ).fetchone()
                )
            db.execute(
                """INSERT OR IGNORE INTO clientes(nombres,apellidos,rut,email,telefono,direccion,comuna_id,comuna_nombre,
              provincia,region,fecha_nacimiento,sexo,email_verificado_at,created_at,updated_at)
              VALUES('Cliente','Demostración','12345678-5','cliente@fitexpress.test','900000000','Calle ficticia 10',1,
              'Providencia','Santiago','Metropolitana','2000-01-01','No especificado',?,?,?)""",
                (now(), now(), now()),
            )
            id = db.execute(
                "SELECT id FROM clientes WHERE email='cliente@fitexpress.test'"
            ).fetchone()[0]
            db.execute(
                "INSERT OR IGNORE INTO usuarios(cliente_id,identificador,password_hash,rol,created_at) VALUES(?,'cliente@fitexpress.test',?,'cliente',?)",
                (id, password_hash(password), now()),
            )
            db.execute(
                "UPDATE usuarios SET password_hash=? WHERE cliente_id=?",
                (password_hash(password), id),
            )
            result["cliente"] = dict(
                db.execute(
                    "SELECT id,identificador,rol,cliente_id FROM usuarios WHERE cliente_id=?",
                    (id,),
                ).fetchone()
            )
            print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
