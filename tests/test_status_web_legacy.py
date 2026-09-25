import sqlite3

from nfe_consulta.seguranca_banco import migrar_banco
from nfe_consulta.web.status_view import read_web_status


CNPJ = "16840128000101"


def test_status_le_banco_sqlcipher_legado_sem_tabela_de_cooldown(tmp_path):
    origem = tmp_path / "legado.db"
    with sqlite3.connect(origem) as conn:
        conn.execute(
            "CREATE TABLE estado_distribuicao("
            "cnpj TEXT PRIMARY KEY, ult_nsu TEXT NOT NULL, max_nsu TEXT NOT NULL, "
            "atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO estado_distribuicao(cnpj, ult_nsu, max_nsu) VALUES (?, ?, ?)",
            (CNPJ, "10".zfill(15), "10".zfill(15)),
        )
        conn.execute(
            "CREATE TABLE pausa_distribuicao("
            "cnpj TEXT PRIMARY KEY, ate_utc TEXT NOT NULL, motivo TEXT NOT NULL)"
        )

    seguro = tmp_path / "legado seguro.db"
    senha = "Senha-Forte-123!"
    migrar_banco(origem, seguro, senha)

    status = read_web_status(seguro, CNPJ, password=senha)

    assert status.database_ready is True
    assert status.ult_nsu == "10".zfill(15)
    assert status.max_nsu == "10".zfill(15)
    assert status.last_attempt is None
    assert status.next_attempt is None
    assert status.can_sync is True
