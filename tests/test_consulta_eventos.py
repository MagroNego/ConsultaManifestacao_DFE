import pytest
import sqlite3

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import InformacaoNota, Manifestacao, RetornoDistribuicao
from nfe_consulta.web.consulta_local import (
    consultar_eventos,
    normalizar_filtros,
)


CNPJ = "16840128000101"
CHAVE = "33260812345678000199550010000917791147439711"


def _chave(numero: int, serie: int = 1) -> str:
    return (
        CHAVE[:22]
        + f"{serie:03d}"
        + f"{numero:09d}"
        + CHAVE[34:]
    )


def _criar_banco(caminho):
    banco = BancoManifestacoes(str(caminho))
    manifestacoes = []
    for indice, (numero, serie, codigo, data) in enumerate(
        (
            (91779, 1, "210210", "2026-09-01T08:00:00-03:00"),
            (91780, 1, "210240", "2026-09-15T09:00:00-03:00"),
            (91781, 2, "210200", "2026-09-30T10:00:00-03:00"),
        ),
        start=1,
    ):
        manifestacoes.append(
            (
                _chave(numero, serie),
                Manifestacao(
                    codigo=codigo,
                    descricao="Evento",
                    data=data,
                    protocolo=f"13526000000000{indice}",
                    nsu=str(600000 + indice),
                    schema="procEventoNFe_v1.00.xsd",
                ),
            )
        )

    banco.salvar_retorno(
        CNPJ,
        RetornoDistribuicao(
            status_codigo=138,
            status_motivo="Documentos localizados",
            ult_nsu="600003".zfill(15),
            max_nsu="600003".zfill(15),
            manifestacoes=tuple(manifestacoes),
            informacoes_notas=(InformacaoNota(_chave(91780), "Fornecedor Teste", True),),
        ),
    )
    banco.fechar()


def test_rejeita_periodo_invertido():
    with pytest.raises(ValueError, match="data inicial"):
        normalizar_filtros(
            data_inicial="2026-09-30",
            data_final="2026-09-01",
        )


def test_filtra_periodo_serie_e_manifestacao(tmp_path):
    caminho = tmp_path / "manifestacoes.db"
    _criar_banco(caminho)

    filtros = normalizar_filtros(
        data_inicial="2026-09-10",
        data_final="2026-09-30",
        serie="2",
        codigo="210200",
    )
    resultado = consultar_eventos(caminho, CNPJ, filtros)

    assert resultado.total == 1
    assert resultado.eventos[0].numero == 91781
    assert resultado.eventos[0].serie == "2"
    assert resultado.eventos[0].codigo == "210200"


def test_paginacao_preserva_total(tmp_path):
    caminho = tmp_path / "manifestacoes.db"
    _criar_banco(caminho)

    filtros = normalizar_filtros()
    primeira = consultar_eventos(
        caminho,
        CNPJ,
        filtros,
        pagina=1,
        por_pagina=2,
    )
    segunda = consultar_eventos(
        caminho,
        CNPJ,
        filtros,
        pagina=2,
        por_pagina=2,
    )

    assert primeira.total == 3
    assert primeira.paginas == 2
    assert len(primeira.eventos) == 2
    assert primeira.primeiro == 1
    assert primeira.ultimo == 2

    assert segunda.total == 3
    assert len(segunda.eventos) == 1
    assert segunda.primeiro == 3
    assert segunda.ultimo == 3


def test_somente_canceladas_combina_com_outros_filtros(tmp_path):
    caminho = tmp_path / "manifestacoes.db"
    _criar_banco(caminho)
    resultado = consultar_eventos(caminho, CNPJ, normalizar_filtros(canceladas="1"))
    assert resultado.total == 1
    assert resultado.eventos[0].numero == 91780
    assert resultado.eventos[0].cancelada
    assert consultar_eventos(caminho, CNPJ, normalizar_filtros(canceladas="1", codigo="210200")).total == 0
    with pytest.raises(ValueError, match="cancelamento"):
        normalizar_filtros(canceladas="qualquer")


def test_filtro_canceladas_em_banco_antigo_sem_tabela(tmp_path):
    caminho = tmp_path / "antigo.db"
    _criar_banco(caminho)
    with sqlite3.connect(caminho) as db:
        db.execute("DROP TABLE informacoes_nfe")
    assert consultar_eventos(caminho, CNPJ, normalizar_filtros()).total == 3
    assert consultar_eventos(caminho, CNPJ, normalizar_filtros(canceladas="1")).total == 0
