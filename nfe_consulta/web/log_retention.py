"""Retenção dos registros operacionais, sem alterar o banco fiscal."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYNC_RETENTION_DAYS = 30
SYNC_ACTIONS = frozenset({'sefaz_sync', 'sefaz_sync_auto', 'sefaz_scheduler'})


def log_instant(line: str, payload: dict) -> datetime | None:
    for key in ('logged_at_utc',):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None:
                    return parsed.astimezone(timezone.utc)
            except (ValueError, OverflowError, OSError):
                pass
    try:
        # Logs antigos usam o horário local do servidor.
        return datetime.strptime(line[:19], '%Y-%m-%d %H:%M:%S').astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def prune_sync_logs(path: Path, *, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=SYNC_RETENTION_DAYS)
    removed = 0
    for candidate in (path, *(path.with_name(f'{path.name}.{i}') for i in range(1, 6))):
        if not candidate.is_file():
            continue
        lines = candidate.read_text(encoding='utf-8').splitlines(keepends=True)
        retained = []
        for line in lines:
            try:
                payload = json.loads(line[line.index('{', 19):])
            except (ValueError, TypeError):
                retained.append(line)
                continue
            instant = log_instant(line, payload) if isinstance(payload, dict) else None
            if (isinstance(payload, dict) and isinstance(payload.get('action'), str)
                    and payload['action'] in SYNC_ACTIONS
                    and instant is not None and instant < cutoff):
                continue
            retained.append(line)
        if len(retained) == len(lines):
            continue
        # Substituição atômica: uma falha não trunca o arquivo original.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                    dir=candidate.parent, prefix=candidate.name + '.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.writelines(retained)
            os.chmod(temporary, candidate.stat().st_mode & 0o777)
            os.replace(temporary, candidate)
            removed += len(lines) - len(retained)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return removed
