"""Agendador interno da sincronização automática da SEFAZ."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Iterable

from nfe_consulta.modelos import NfeConsumoIndevidoErro, NfeLimiteConsultaErro
from nfe_consulta.web.sync_runtime import sincronizar_configurado


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


async def executar_sincronizacao_automatica(app) -> None:
    """Executa uma sincronização automática respeitando o lock da Web."""
    settings = app.state.settings
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
        await executar_sincronizacao_automatica(app)
