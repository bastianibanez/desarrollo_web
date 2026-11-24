"""Administración local: ejecutar dentro del contenedor clients (auth para expirar-sesiones)."""

import argparse
import getpass
import json
import sys

from services.common import Context, now, password_hash

DEMO = "demo@fitexpress.cl"


def expire_sessions(ctx, usuario_id=None):
    moment = now()
    sql, params = "UPDATE sesiones SET expira_at=? WHERE expira_at>?", [moment, moment]
    if usuario_id:
        sql += " AND usuario_id=?"
        params.append(usuario_id)
    with ctx.transaction() as db:
        return db.execute(sql, params).rowcount


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["create-admin", "seed-demo", "mensajes", "expirar-sesiones"]
    )
    parser.add_argument("--identificador", default="admin@fitexpress.test")
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument("--usuario-id", type=int)
    args = parser.parse_args()
    ctx = Context("auth" if args.command == "expirar-sesiones" else "clients")
    ctx.initialize()
    if args.command == "expirar-sesiones":
        print(f"Sesiones expiradas: {expire_sessions(ctx, args.usuario_id)}")
        return
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
    minimum = 12 if args.command == "create-admin" else 6
    password = (
        sys.stdin.readline().rstrip("\n")
        if args.password_stdin
        else getpass.getpass(f"Contraseña (mínimo {minimum} caracteres): ")
    )
    if len(password) < minimum:
        parser.error(f"La contraseña requiere al menos {minimum} caracteres")
    with ctx.transaction() as db:
        if args.command == "create-admin":
            db.execute(
                "INSERT INTO usuarios(identificador,password_hash,rol,created_at) VALUES(?,?,'administrador',?)",
                (args.identificador.lower(), password_hash(password), now()),
            )
            print("Administrador creado.")
        else:
            db.execute(
                """INSERT OR IGNORE INTO clientes(nombres,apellidos,rut,email,telefono,direccion,comuna_id,comuna_nombre,
              provincia,region,fecha_nacimiento,sexo,email_verificado_at,created_at,updated_at)
              VALUES('Cuenta','Demo','11111111-1',?,'900000000','Calle ficticia 10',1,
              'Providencia','Santiago','Metropolitana','2000-01-01','No especificado',?,?,?)""",
                (DEMO, now(), now(), now()),
            )
            id = db.execute(
                "SELECT id FROM clientes WHERE email=?", (DEMO,)
            ).fetchone()[0]
            db.execute(
                "INSERT OR IGNORE INTO usuarios(cliente_id,identificador,password_hash,rol,created_at) VALUES(?,?,?,'cliente',?)",
                (id, DEMO, password_hash(password), now()),
            )
            db.execute(
                "UPDATE usuarios SET password_hash=? WHERE cliente_id=?",
                (password_hash(password), id),
            )
            print(
                json.dumps(
                    dict(
                        db.execute(
                            "SELECT id,identificador,rol,cliente_id FROM usuarios WHERE cliente_id=?",
                            (id,),
                        ).fetchone()
                    ),
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
