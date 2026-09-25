import sqlite3

import pytest

from nfe_consulta.seguranca_banco import abrir_banco, migrar_banco


def test_somente_leitura_sqlite_bloqueia_escrita(tmp_path):
    caminho = tmp_path / "banco com espacos.db"
    with sqlite3.connect(caminho) as conn:
        conn.execute("CREATE TABLE teste(id INTEGER)")
        conn.execute("INSERT INTO teste VALUES (1)")

    conn = abrir_banco(caminho, somente_leitura=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM teste").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly|query_only"):
            conn.execute("INSERT INTO teste VALUES (2)")
    finally:
        conn.close()


def test_somente_leitura_sqlcipher_funciona_em_caminho_com_espacos(tmp_path):
    origem = tmp_path / "origem banco.db"
    with sqlite3.connect(origem) as conn:
        conn.execute("CREATE TABLE teste(id INTEGER)")
        conn.execute("INSERT INTO teste VALUES (1)")

    destino = tmp_path / "banco seguro com espacos.db"
    senha = "Senha-Forte-123!"
    migrar_banco(origem, destino, senha)

    conn = abrir_banco(destino, senha, somente_leitura=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM teste").fetchone()[0] == 1
        with pytest.raises(Exception):
            conn.execute("INSERT INTO teste VALUES (2)")
    finally:
        conn.close()
