"""Resumo das ações administrativas para administradores autenticados."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nfe_consulta.web.sync_history import _tail_lines


LABELS = {
    "sefaz_sync": "Sincronização SEFAZ",
    "admin_accounts": "Acesso administrativo",
    "email_recipients": "Destinatários dos alertas",
    "xml_import": "Importação de XML",
    "xml_download": "Download de XML",
    "xml_export": "Exportação do leitor XML",
    "excel_chaves": "Exportação por chaves",
    "export_eventos_excel": "Exportação de manifestações",
}
OPERATIONS = {
    "create": "Conta cadastrada",
    "reset": "Senha alterada",
    "activate": "Conta ativada",
    "deactivate": "Conta desativada",
    "role": "Perfil alterado",
}


@dataclass(frozen=True)
class AdminHistoryItem:
    when: str
    username: str
    action: str
    result: str
    detail: str


def read_admin_history(path: Path, limit: int = 50) -> tuple[AdminHistoryItem, ...]:
    items: list[AdminHistoryItem] = []
    for candidate in (path, *(path.with_name(f"{path.name}.{i}") for i in range(1, 6))):
        if not candidate.is_file():
            continue
        for line in reversed(_tail_lines(candidate)):
            if len(items) >= limit:
                return tuple(items)
            try:
                when = line[:19]
                datetime.strptime(when, "%Y-%m-%d %H:%M:%S")
                payload = json.loads(line[line.index("{", 19):])
            except (ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            action = payload.get("action")
            result = payload.get("result")
            if action not in LABELS or result not in {"ok", "erro"}:
                continue
            username = payload.get("user")
            if not isinstance(username, str):
                continue
            detail = ""
            if action == "admin_accounts":
                operation = payload.get("operation")
                target = payload.get("target")
                detail = OPERATIONS.get(operation, "Alteração de conta")
                if isinstance(target, str) and len(target) <= 64:
                    detail += f" · {target}"
            elif action == "email_recipients" and isinstance(payload.get("count"), int):
                detail = f"{payload['count']} destinatário(s)"
            elif action == "sefaz_sync" and result == "ok":
                count = payload.get("eventos_novos")
                if isinstance(count, int):
                    detail = f"{count} manifestação(ões) nova(s)"
            items.append(AdminHistoryItem(
                when=when,
                username=username,
                action=LABELS[action],
                result="Concluída" if result == "ok" else "Falhou",
                detail=detail or "—",
            ))
    return tuple(items)
