"""Consultas somente leitura no banco local de manifestações."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from pathlib import Path

from nfe_consulta.seguranca_banco import abrir_banco


TIPOS_MANIFESTACAO = {
    "210200": "Confirmação da Operação",
    "210210": "Ciência da Operação",
    "210220": "Desconhecimento da Operação",
    "210240": "Operação não Realizada",
}


@dataclass(frozen=True)
class FiltrosEventos:
    data_inicial: date | None = None
    data_final: date | None = None
    numero: int | None = None
    serie: int | None = None
    chave: str | None = None
    codigo: str | None = None

    @property
    def data_inicial_texto(self) -> str:
        return self.data_inicial.isoformat() if self.data_inicial else ""

    @property
    def data_final_texto(self) -> str:
        return self.data_final.isoformat() if self.data_final else ""

    @property
    def numero_texto(self) -> str:
        return str(self.numero) if self.numero is not None else ""

    @property
    def serie_texto(self) -> str:
        return str(self.serie) if self.serie is not None else ""


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
    recebido_em: str = ""

    @property
    def data_label(self) -> str:
        return _data_label(self.data)

    @property
    def recebido_label(self) -> str:
        return _data_label(self.recebido_em, recebido_utc=True)


@dataclass(frozen=True)
class ResultadoEventos:
    eventos: tuple[EventoNota, ...]
    total: int
    pagina: int
    por_pagina: int

    @property
    def paginas(self) -> int:
        return ceil(self.total / self.por_pagina) if self.total else 0

    @property
    def primeiro(self) -> int:
        return ((self.pagina - 1) * self.por_pagina + 1) if self.total else 0

    @property
    def ultimo(self) -> int:
        return min(self.pagina * self.por_pagina, self.total) if self.total else 0


def _data_label(valor: str, *, recebido_utc: bool = False) -> str:
    valor = (valor or "").strip()
    if not valor:
        return "—"
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return valor
    sufixo = " UTC" if recebido_utc and instante.tzinfo is None else ""
    return instante.strftime("%d/%m/%Y %H:%M:%S") + sufixo


def _parse_data(valor: str, rotulo: str) -> date | None:
    valor = valor.strip()
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f"{rotulo} inválida.") from exc


def normalizar_filtros(
    *,
    data_inicial: str = "",
    data_final: str = "",
    numero: str = "",
    serie: str = "",
    chave: str = "",
    codigo: str = "",
) -> FiltrosEventos:
    inicio = _parse_data(data_inicial, "Data inicial")
    fim = _parse_data(data_final, "Data final")
    if inicio and fim and inicio > fim:
        raise ValueError("A data inicial não pode ser posterior à data final.")

    numero_limpo = numero.strip()
    if numero_limpo and not numero_limpo.isdigit():
        raise ValueError("Informe somente números no campo Número da NF.")
    numero_valor = int(numero_limpo) if numero_limpo else None
    if numero_valor is not None and not 1 <= numero_valor <= 999_999_999:
        raise ValueError("Número da NF deve estar entre 1 e 999999999.")

    serie_limpa = serie.strip()
    if serie_limpa and not serie_limpa.isdigit():
        raise ValueError("Informe somente números no campo Série.")
    serie_valor = int(serie_limpa) if serie_limpa else None
    if serie_valor is not None and not 0 <= serie_valor <= 999:
        raise ValueError("Série deve estar entre 0 e 999.")

    chave_limpa = "".join(chave.split())
    if chave_limpa:
        if not chave_limpa.isdigit() or len(chave_limpa) != 44:
            raise ValueError("A chave da NF-e deve conter exatamente 44 dígitos.")
    else:
        chave_limpa = None

    codigo_limpo = codigo.strip()
    if codigo_limpo and codigo_limpo not in TIPOS_MANIFESTACAO:
        raise ValueError("Tipo de manifestação inválido.")

    return FiltrosEventos(
        data_inicial=inicio,
        data_final=fim,
        numero=numero_valor,
        serie=serie_valor,
        chave=chave_limpa,
        codigo=codigo_limpo or None,
    )


def _where_eventos(
    cnpj: str,
    filtros: FiltrosEventos,
) -> tuple[str, list[object]]:
    clausulas = ["cnpj = ?"]
    parametros: list[object] = [cnpj]

    if filtros.data_inicial:
        clausulas.append("data_evento >= ?")
        parametros.append(filtros.data_inicial.isoformat())

    if filtros.data_final:
        dia_seguinte = filtros.data_final + timedelta(days=1)
        clausulas.append("data_evento < ?")
        parametros.append(dia_seguinte.isoformat())

    if filtros.numero is not None:
        clausulas.append("CAST(SUBSTR(chave, 26, 9) AS INTEGER) = ?")
        parametros.append(filtros.numero)

    if filtros.serie is not None:
        clausulas.append("CAST(SUBSTR(chave, 23, 3) AS INTEGER) = ?")
        parametros.append(filtros.serie)

    if filtros.chave:
        clausulas.append("chave = ?")
        parametros.append(filtros.chave)

    if filtros.codigo:
        clausulas.append("codigo = ?")
        parametros.append(filtros.codigo)

    return " AND ".join(clausulas), parametros


def _evento_da_linha(linha) -> EventoNota:
    chave, codigo, descricao, data_evento, protocolo, nsu, recebido_em = linha
    numero = int(chave[25:34])
    serie = chave[22:25].lstrip("0") or "0"
    return EventoNota(
        numero=numero,
        serie=serie,
        chave=chave,
        codigo=codigo,
        descricao=TIPOS_MANIFESTACAO.get(codigo, descricao),
        data=data_evento,
        protocolo=protocolo,
        nsu=nsu,
        recebido_em=recebido_em,
    )


def consultar_eventos(
    database_path: Path,
    cnpj: str,
    filtros: FiltrosEventos,
    *,
    password: str | None = None,
    pagina: int = 1,
    por_pagina: int = 100,
) -> ResultadoEventos:
    """Consulta eventos com filtros e paginação sem acessar a SEFAZ."""
    if pagina < 1:
        raise ValueError("Página inválida.")
    if not 1 <= por_pagina <= 500:
        raise ValueError("Quantidade por página inválida.")

    where, parametros = _where_eventos(cnpj, filtros)
    conexao = abrir_banco(database_path, password, somente_leitura=True)
    try:
        total = int(
            conexao.execute(
                f"SELECT COUNT(*) FROM manifestacoes WHERE {where}",
                parametros,
            ).fetchone()[0]
        )

        paginas = ceil(total / por_pagina) if total else 0
        pagina_efetiva = min(pagina, paginas) if paginas else 1
        offset = (pagina_efetiva - 1) * por_pagina

        linhas = conexao.execute(
            f"""
            SELECT
                chave,
                codigo,
                descricao,
                data_evento,
                protocolo,
                nsu,
                recebido_em
            FROM manifestacoes
            WHERE {where}
            ORDER BY data_evento DESC, CAST(nsu AS INTEGER) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*parametros, por_pagina, offset],
        ).fetchall()
    finally:
        conexao.close()

    return ResultadoEventos(
        eventos=tuple(_evento_da_linha(linha) for linha in linhas),
        total=total,
        pagina=pagina_efetiva,
        por_pagina=por_pagina,
    )


def consultar_eventos_exportacao(
    database_path: Path,
    cnpj: str,
    filtros: FiltrosEventos,
    *,
    password: str | None = None,
    limite: int = 200_000,
) -> tuple[EventoNota, ...]:
    """Retorna todos os eventos filtrados para exportação."""
    where, parametros = _where_eventos(cnpj, filtros)
    conexao = abrir_banco(database_path, password, somente_leitura=True)
    try:
        total = int(
            conexao.execute(
                f"SELECT COUNT(*) FROM manifestacoes WHERE {where}",
                parametros,
            ).fetchone()[0]
        )
        if total > limite:
            raise ValueError(
                f"A consulta retornou {total:,} eventos. "
                "Refine os filtros antes de exportar."
            )

        linhas = conexao.execute(
            f"""
            SELECT
                chave,
                codigo,
                descricao,
                data_evento,
                protocolo,
                nsu,
                recebido_em
            FROM manifestacoes
            WHERE {where}
            ORDER BY data_evento DESC, CAST(nsu AS INTEGER) DESC, id DESC
            """,
            parametros,
        ).fetchall()
    finally:
        conexao.close()

    return tuple(_evento_da_linha(linha) for linha in linhas)


def consultar_numero_nota(
    database_path: Path,
    cnpj: str,
    numero: int,
    *,
    password: str | None = None,
    limite: int = 200,
) -> tuple[EventoNota, ...]:
    """Compatibilidade: busca eventos de uma única NF no banco local."""
    filtros = FiltrosEventos(numero=numero)
    resultado = consultar_eventos(
        database_path,
        cnpj,
        filtros,
        password=password,
        pagina=1,
        por_pagina=min(max(limite, 1), 500),
    )
    return resultado.eventos
