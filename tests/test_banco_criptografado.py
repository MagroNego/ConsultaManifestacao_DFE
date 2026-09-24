import sqlite3

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.seguranca_banco import abrir_banco, criptografado, migrar_banco
from nfe_consulta.status import consultar_status


def test_migracao_preserva_eventos_e_cursor_sem_alterar_origem(tmp_path):
    origem = tmp_path / "historico.db"
    destino = tmp_path / "historico_seguro.db"
    senha = "exemplo bem comprido!"
    banco = BancoManifestacoes(str(origem))
    with banco.conexao:
        banco.conexao.execute(
            "INSERT INTO estado_distribuicao(cnpj,ult_nsu,max_nsu) VALUES(?,?,?)",
            ("16840128000101", "000000000563245", "000000000563245"))
        banco.conexao.execute(
            "INSERT INTO manifestacoes(cnpj,chave,codigo,descricao,data_evento,protocolo,nsu,schema_xml) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("16840128000101", "1"*44, "210200", "Confirmacao", "2026-09-01", "protocolo", "563245", "resEvento"))
    banco.fechar()
    migrar_banco(origem, destino, senha)
    assert origem.read_bytes().startswith(b"SQLite format 3\x00")
    assert not destino.read_bytes().startswith(b"SQLite format 3\x00")
    assert criptografado(destino)
    with pytest.raises(ValueError, match="Senha incorreta"):
        abrir_banco(destino, "senha errada")
    with pytest.raises(ValueError, match="destino já existe"):
        migrar_banco(origem, destino, senha)
    protegido = BancoManifestacoes(str(destino), senha)
    assert protegido.obter_estado("16840128000101") == ("000000000563245", "000000000563245")
    assert protegido.conexao.execute("SELECT chave FROM manifestacoes").fetchone() == ("1"*44,)
    protegido.fechar()
    assert "000000000563245" in consultar_status(str(destino), "16840128000101", senha=senha)
    with pytest.raises(sqlite3.DatabaseError):
        with sqlite3.connect(destino) as simples:
            simples.execute("SELECT * FROM manifestacoes").fetchone()
