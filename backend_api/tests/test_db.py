import sqlite3

import pytest

TABLAS = {
    "categorias",
    "productos",
    "combos",
    "lineas_combo",
    "comunas",
    "costos_envio",
    "clientes",
    "ordenes",
    "lineas_orden",
}


@pytest.fixture
def db_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("TIENDA_DB", str(tmp_path / "t.db"))
    import db

    db.inicializar()
    return db


def contar(conn, tabla):
    return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def test_crea_tablas(db_tmp):
    conn = db_tmp.conectar()
    nombres = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert nombres == TABLAS


def test_seed_completo(db_tmp):
    conn = db_tmp.conectar()
    assert contar(conn, "categorias") == 3
    assert contar(conn, "comunas") == 9
    assert contar(conn, "costos_envio") == 9
    assert contar(conn, "productos") == 8
    assert contar(conn, "combos") == 2
    assert contar(conn, "lineas_combo") == 5


def test_seed_idempotente(db_tmp):
    db_tmp.inicializar()
    conn = db_tmp.conectar()
    assert contar(conn, "productos") == 8
    assert contar(conn, "comunas") == 9


def test_foreign_keys_activas(db_tmp):
    conn = db_tmp.conectar()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO productos (nombre, precio, stock, categoria_id) VALUES ('x', 1, 1, 999)"
        )
