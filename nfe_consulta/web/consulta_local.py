"""Consulta rápida somente leitura no banco local."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nfe_consulta.seguranca_banco import abrir_banco


@dataclass(frozen=True)
class EventoNota:
    numero: int
    serie: str
    chave: str
    codigo: str
    descricao: str
    data: str
    protocolo: str
    nsu: str


def consultar_numero_nota(
    database_path: Path,
    cnpj: str,
    numero: int,
    *,
    password: str | None = None,
    limite: int = 200,
) -> tuple[EventoNota, ...]:
    """Busca eventos pelo nNF embutido na chave de acesso, sem acessar a SEFAZ."""
    if numero < 1 or numero > 999_999_999:
        raise ValueError("Número da NF deve estar entre 1 e 999999999.")
    if limite < 1 or limite > 1000:
        raise ValueError("Limite inválido.")

    conexao = abrir_banco(database_path, password, somente_leitura=True)
    try:
        linhas = conexao.execute(
            """
            SELECT
                chave,
                codigo,
                descricao,
                data_evento,
                protocolo,
                nsu
            FROM manifestacoes
            WHERE cnpj = ?
              AND CAST(SUBSTR(chave, 26, 9) AS INTEGER) = ?
            ORDER BY
                chave,
                data_evento DESC,
                CAST(nsu AS INTEGER) DESC,
                id DESC
            LIMIT ?
            """,
            (cnpj, numero, limite),
        ).fetchall()
    finally:
        conexao.close()

    return tuple(
        EventoNota(
            numero=numero,
            serie=chave[22:25].lstrip("0") or "0",
            chave=chave,
            codigo=codigo,
            descricao=descricao,
            data=data_evento,
            protocolo=protocolo,
            nsu=nsu,
        )
        for chave, codigo, descricao, data_evento, protocolo, nsu in linhas
    )
