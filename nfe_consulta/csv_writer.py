import csv
from typing import TextIO

from nfe_consulta.modelos import ResultadoConsulta
from nfe_consulta.validacao import numero_e_serie

CABECALHO = [
    "chave",
    "numero_nfe",
    "serie_nfe",
    "manifestacao_codigo",
    "manifestacao_descricao",
    "manifestacao_data",
    "manifestacao_protocolo",
    "manifestacao_nsu",
    "quantidade_eventos",
    "historico",
    "cobertura",
    "erro",
]


def _seguro_csv(valor):
    """Evita interpretacao de texto recebido como formula ao abrir no Excel."""
    if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + valor
    return valor


def gravar_csv(arquivo: TextIO, resultados: list, cobertura: str = "Historico local") -> None:
    writer = csv.DictWriter(arquivo, fieldnames=CABECALHO, delimiter=";")
    writer.writeheader()

    for r in resultados:
        numero, serie = numero_e_serie(r.chave)
        base = {
            "chave": r.chave,
            "numero_nfe": numero,
            "serie_nfe": serie,
            "quantidade_eventos": len(r.manifestacoes),
            "historico": " | ".join(
                f"{m.data} - {m.descricao}" for m in r.manifestacoes
            ),
            "cobertura": cobertura,
            "erro": r.erro if r.erro else "",
        }

        if not r.manifestacoes:
            row = dict(base)
            row.update(
                {
                    "manifestacao_codigo": "",
                    "manifestacao_data": "",
                    "manifestacao_protocolo": "",
                    "manifestacao_nsu": "",
                    "manifestacao_descricao": "Sem manifestacao localizada no historico local",
                }
            )
            writer.writerow({campo: _seguro_csv(valor) for campo, valor in row.items()})
        else:
            m = r.manifestacoes[-1]
            row = dict(base)
            row.update(
                {
                    "manifestacao_codigo": m.codigo,
                    "manifestacao_descricao": m.descricao,
                    "manifestacao_data": m.data,
                    "manifestacao_protocolo": m.protocolo,
                    "manifestacao_nsu": m.nsu,
                }
            )
            writer.writerow({campo: _seguro_csv(valor) for campo, valor in row.items()})
