from pathlib import Path
from typing import Callable

from nfe_consulta.modelos import (
    NfeChaveInvalidaErro,
    NfeConsultaErro,
    ResultadoConsulta,
)
from nfe_consulta.validacao import validar_chave

MAX_TXT_BYTES = 2 * 1024 * 1024
MAX_CHAVES = 10_000


def ler_chaves(caminho: str) -> list:
    arquivo = Path(caminho)
    if arquivo.stat().st_size > MAX_TXT_BYTES:
        raise NfeConsultaErro("TXT de chaves excede 2 MiB")
    linhas = arquivo.read_text(encoding="utf-8-sig").splitlines()
    chaves = [l.strip() for l in linhas if l.strip()]
    if len(chaves) > MAX_CHAVES:
        raise NfeConsultaErro("TXT de chaves excede 10.000 linhas")
    return chaves


def processar_lote(
    chaves: list,
    consultar_fn: Callable,
    progresso_fn: Callable | None = None,
) -> list:
    resultados = []
    total = len(chaves)
    for idx, chave_raw in enumerate(chaves, 1):
        try:
            chave = validar_chave(chave_raw)
            resultado = consultar_fn(chave)
            resultados.append(resultado)
        except NfeChaveInvalidaErro as e:
            resultados.append(
                ResultadoConsulta(
                    chave=chave_raw,
                    status_codigo=0,
                    status_motivo="",
                    protocolo_nfe=None,
                    manifestacoes=(),
                    erro=str(e),
                )
            )
        except NfeConsultaErro as e:
            resultados.append(
                ResultadoConsulta(
                    chave=chave_raw,
                    status_codigo=0,
                    status_motivo="",
                    protocolo_nfe=None,
                    manifestacoes=(),
                    erro=str(e),
                )
            )
        except Exception as e:
            resultados.append(
                ResultadoConsulta(
                    chave=chave_raw,
                    status_codigo=0,
                    status_motivo="",
                    protocolo_nfe=None,
                    manifestacoes=(),
                    erro=f"Erro inesperado: {e}",
                )
            )
        if progresso_fn:
            progresso_fn(idx, total)
    return resultados
