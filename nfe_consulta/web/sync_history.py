"""Histórico público e resumido das sincronizações no log de auditoria."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_REASONS = {
    "consumo_indevido_656": "SEFAZ: consumo indevido (656)",
    "NfeConsumoIndevidoErro": "SEFAZ: consumo indevido (656)",
    "cooldown": "Intervalo entre consultas ainda ativo",
    "sync_in_progress": "Outra sincronização em andamento",
    "FileNotFoundError": "Banco ou certificado não encontrado",
    "NfeErroCertificado": "Falha no certificado",
    "NfeErroComunicacao": "Falha de comunicação com a SEFAZ",
    "NfeErroResposta": "Resposta inválida da SEFAZ",
}


@dataclass(frozen=True)
class SyncHistoryItem:
    when: str
    origin: str
    result: str
    lots: int | None
    new_events: int | None
    detail: str


def _tail_lines(path: Path, max_bytes: int = 6 * 1024 * 1024) -> list[str]:
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - max_bytes))
        data = stream.read()
    if size > max_bytes:
        data = data.partition(b"\n")[2]
    return data.decode("utf-8", errors="replace").splitlines()


def read_sync_history(path: Path, limit: int = 10) -> tuple[SyncHistoryItem, ...]:
    """Lê apenas ações SEFAZ; nunca expõe usuário, IP ou mensagem bruta do log."""
    items: list[SyncHistoryItem] = []
    for candidate in (path, *(path.with_name(f"{path.name}.{i}") for i in range(1, 6))):
        if not candidate.is_file():
            continue
        for line in reversed(_tail_lines(candidate)):
            if len(items) >= limit:
                return tuple(items)
            try:
                timestamp = line[:19]
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                json_start = line.index("{", 19)
                payload = json.loads(line[json_start:])
            except (ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("action") not in {"sefaz_sync", "sefaz_sync_auto"}:
                continue
            outcome = payload.get("result")
            if outcome not in {"ok", "erro", "ignorado"}:
                continue
            reason = payload.get("reason") if isinstance(payload.get("reason"), str) else None
            detail = _REASONS.get(reason, "Falha na sincronização") if outcome == "erro" else ""
            incomplete = outcome == "ok" and payload.get("completo") is False
            if incomplete:
                detail = "Ainda há lotes a consultar"
            if outcome == "ignorado":
                detail = _REASONS.get(reason, "Tentativa não executada")
            items.append(SyncHistoryItem(
                when=timestamp,
                origin="Automática" if payload["action"] == "sefaz_sync_auto" else "Manual",
                result=("Parcial" if incomplete else
                        {"ok": "Concluída", "erro": "Falhou", "ignorado": "Não executada"}[outcome]),
                lots=payload.get("lotes") if isinstance(payload.get("lotes"), int) else None,
                new_events=payload.get("eventos_novos") if isinstance(payload.get("eventos_novos"), int) else None,
                detail=detail,
            ))
    return tuple(items)
