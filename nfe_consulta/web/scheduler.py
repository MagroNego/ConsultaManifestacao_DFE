"""Agendador interno da sincronização automática da SEFAZ."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Iterable

from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.modelos import NfeConsumoIndevidoErro, NfeLimiteConsultaErro
from nfe_consulta.seguranca_banco import abrir_banco
from nfe_consulta.web.sync_runtime import (
    caminho_banco_configurado,
    sincronizar_configurado,
)


def proxima_execucao(
    agora: datetime,
    *,
    hora: int,
    minuto: int,
    dias_semana: Iterable[int],
) -> datetime:
    """Calcula a próxima execução no fuso horário do servidor.

    Segunda-feira = 0 e domingo = 6.
    """
    dias = frozenset(dias_semana)
    if not dias:
        raise ValueError("Ao menos um dia da semana deve ser configurado.")
    if any(dia < 0 or dia > 6 for dia in dias):
        raise ValueError("Dias da semana devem estar entre 0 e 6.")
    if not 0 <= hora <= 23:
        raise ValueError("Hora inválida.")
    if not 0 <= minuto <= 59:
        raise ValueError("Minuto inválido.")

    for deslocamento in range(8):
        dia = agora.date() + timedelta(days=deslocamento)
        if dia.weekday() not in dias:
            continue
        candidato = datetime.combine(
            dia,
            datetime.min.time(),
            tzinfo=agora.tzinfo,
        ).replace(hour=hora, minute=minuto)
        if candidato > agora:
            return candidato

    raise RuntimeError("Não foi possível calcular a próxima sincronização.")


def deve_recuperar_execucao(
    agora: datetime,
    ultima_execucao_local: date | None,
    *,
    hora: int,
    minuto: int,
    dias_semana: Iterable[int],
) -> bool:
    """Indica se o serviço subiu depois do horário e precisa recuperar o dia."""
    dias = frozenset(dias_semana)
    if agora.weekday() not in dias:
        return False

    horario = agora.replace(
        hour=hora,
        minute=minuto,
        second=0,
        microsecond=0,
    )
    if agora < horario:
        return False

    return ultima_execucao_local != agora.date()


def _garantir_tabela_agendamento(conexao) -> None:
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS controle_agendamento (
            cnpj TEXT PRIMARY KEY,
            ultima_execucao_local TEXT NOT NULL,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conexao.commit()


def ultima_execucao_agendada(settings) -> date | None:
    """Lê do banco a última data local em que o agendador foi disparado."""
    banco = caminho_banco_configurado(settings)
    if not banco.is_file():
        return None

    conexao = abrir_banco(
        banco,
        settings.current_database_password(),
    )
    try:
        _garantir_tabela_agendamento(conexao)
        linha = conexao.execute(
            "SELECT ultima_execucao_local FROM controle_agendamento "
            "WHERE cnpj = ?",
            (CNPJ_PADRAO,),
        ).fetchone()
    finally:
        conexao.close()

    if not linha:
        return None
    return date.fromisoformat(linha[0])


def registrar_execucao_agendada(settings, dia_local: date) -> None:
    """Marca o disparo antes de acessar a SEFAZ para evitar repetição em reinícios."""
    banco = caminho_banco_configurado(settings)
    if not banco.is_file():
        raise FileNotFoundError(f"Banco configurado não encontrado: {banco}")

    conexao = abrir_banco(
        banco,
        settings.current_database_password(),
    )
    try:
        _garantir_tabela_agendamento(conexao)
        with conexao:
            conexao.execute(
                """
                INSERT INTO controle_agendamento(cnpj, ultima_execucao_local)
                VALUES (?, ?)
                ON CONFLICT(cnpj) DO UPDATE SET
                    ultima_execucao_local = excluded.ultima_execucao_local,
                    atualizado_em = CURRENT_TIMESTAMP
                """,
                (CNPJ_PADRAO, dia_local.isoformat()),
            )
    finally:
        conexao.close()


async def executar_sincronizacao_automatica(
    app,
    *,
    dia_agendado: date | None = None,
) -> None:
    """Executa uma sincronização automática respeitando lock, cooldown e persistência."""
    settings = app.state.settings
    dia = dia_agendado or datetime.now().astimezone().date()

    try:
        await asyncio.to_thread(
            registrar_execucao_agendada,
            settings,
            dia,
        )
    except Exception as exc:
        app.state.audit.write_system(
            "sefaz_sync_auto",
            "erro",
            reason=f"schedule_state_{type(exc).__name__}",
        )
        return

    lock = app.state.sync_lock
    if not lock.acquire(blocking=False):
        app.state.audit.write_system(
            "sefaz_sync_auto",
            "ignorado",
            reason="sync_in_progress",
        )
        return

    try:
        try:
            resumo = await asyncio.to_thread(
                sincronizar_configurado,
                settings,
                max_lotes=settings.auto_sync_max_lotes,
                audit=app.state.audit,
            )
        except NfeLimiteConsultaErro:
            app.state.audit.write_system(
                "sefaz_sync_auto",
                "ignorado",
                reason="cooldown",
            )
            return
        except NfeConsumoIndevidoErro:
            app.state.audit.write_system(
                "sefaz_sync_auto",
                "erro",
                reason="consumo_indevido_656",
            )
            return
        except Exception as exc:
            app.state.audit.write_system(
                "sefaz_sync_auto",
                "erro",
                reason=type(exc).__name__,
            )
            return

        app.state.audit.write_system(
            "sefaz_sync_auto",
            "ok",
            lotes=resumo.lotes,
            eventos_novos=resumo.eventos_novos,
            ult_nsu=resumo.ult_nsu,
            max_nsu=resumo.max_nsu,
            completo=resumo.completo,
            cache=resumo.cache,
            cooldown_minutos=settings.sync_cooldown_minutes,
        )
    finally:
        lock.release()


async def loop_sincronizacao_automatica(app) -> None:
    """Mantém a rotina diária enquanto o processo Web estiver ativo."""
    settings = app.state.settings

    agora = datetime.now().astimezone()
    try:
        ultima = await asyncio.to_thread(
            ultima_execucao_agendada,
            settings,
        )
    except Exception as exc:
        ultima = None
        app.state.audit.write_system(
            "sefaz_scheduler",
            "erro",
            reason=f"schedule_state_{type(exc).__name__}",
        )

    if deve_recuperar_execucao(
        agora,
        ultima,
        hora=settings.auto_sync_hour,
        minuto=settings.auto_sync_minute,
        dias_semana=settings.auto_sync_weekdays,
    ):
        app.state.audit.write_system(
            "sefaz_scheduler",
            "recuperacao",
            dia=agora.date().isoformat(),
        )
        await executar_sincronizacao_automatica(
            app,
            dia_agendado=agora.date(),
        )

    while True:
        agora = datetime.now().astimezone()
        proxima = proxima_execucao(
            agora,
            hora=settings.auto_sync_hour,
            minuto=settings.auto_sync_minute,
            dias_semana=settings.auto_sync_weekdays,
        )
        app.state.auto_sync_next_at = proxima

        espera = max(1.0, (proxima - agora).total_seconds())
        await asyncio.sleep(espera)
        await executar_sincronizacao_automatica(
            app,
            dia_agendado=proxima.date(),
        )
