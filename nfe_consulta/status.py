"""Leitura local do cursor de distribuição, sem modificar o banco ou acessar a SEFAZ."""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from nfe_consulta.seguranca_banco import abrir_banco


def _hora_local(instante: datetime) -> str:
    return instante.astimezone().strftime("%d/%m/%Y %H:%M:%S %Z%z")


def consultar_status(caminho: str, cnpj: str, agora: datetime | None = None,
                    senha: str | None = None) -> str:
    """Resume a última sincronização; não afirma que o estado atual da SEFAZ é conhecido."""
    arquivo = Path(caminho).expanduser()
    if not arquivo.is_file():
        return f"Banco nao encontrado: {arquivo}. Nenhuma sincronizacao registrada aqui."

    agora = agora or datetime.now(timezone.utc)
    with closing(abrir_banco(arquivo, senha, somente_leitura=True)) as conexao:
        try:
            linha = conexao.execute(
                "SELECT ult_nsu, max_nsu, atualizado_em FROM estado_distribuicao WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            return f"Banco sem historico de sincronizacao para este aplicativo: {arquivo}."
        try:
            pausa = conexao.execute(
                "SELECT ate_utc, motivo FROM pausa_distribuicao WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            pausa = None

    linhas = [f"Banco: {arquivo}", f"CNPJ: {cnpj}"]
    pausa_ate = datetime.fromisoformat(pausa[0]) if pausa else None
    if not linha:
        linhas.append("Sem sincronizacao registrada para este CNPJ neste banco.")
    else:
        ult, maximo, atualizado = linha
        horario = datetime.strptime(atualizado, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        linhas.extend((
            f"Ultima resposta da SEFAZ salva: {_hora_local(horario)} (horario local)",
            f"ultNSU salvo: {ult} | maxNSU conhecido: {maximo}",
        ))
        if int(ult) < int(maximo):
            linhas.append("Sincronizacao parcial: ainda ha NSUs ate o maximo conhecido. Execute a opcao 1 com este banco para continuar.")
        else:
            linhas.append("Fila percorrida ate o maxNSU conhecido naquela resposta. Eventos novos podem ter surgido depois.")
            proxima = horario + timedelta(hours=1)
            if pausa_ate and pausa_ate > proxima:
                proxima = pausa_ate
            if agora < proxima:
                linhas.append(f"Proxima verificacao recomendada a partir de {_hora_local(proxima)} (horario local).")
            else:
                linhas.append("Ja pode executar a opcao 1 para verificar se existem novidades na SEFAZ.")

    if pausa:
        if pausa_ate > agora:
            linhas.append(f"Pausa por {pausa[1]}: aguarde ate {_hora_local(pausa_ate)} (horario local).")
        else:
            linhas.append(f"Ultima rejeicao registrada (pausa encerrada): {pausa[1]}")
    linhas.append("Este status le apenas o banco local; use a opcao 1 para conferir a SEFAZ quando permitido.")
    return "\n".join(linhas)
