"""Estado estruturado do banco para a interface web."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nfe_consulta.seguranca_banco import abrir_banco


@dataclass(frozen=True)
class WebStatus:
    database_ready: bool
    updated_at: datetime | None
    ult_nsu: str | None
    max_nsu: str | None
    last_attempt: datetime | None
    next_attempt: datetime | None
    pause_until: datetime | None
    pause_reason: str | None

    @property
    def complete(self) -> bool:
        return bool(self.ult_nsu and self.max_nsu and self.ult_nsu == self.max_nsu)

    @property
    def cooldown_active(self) -> bool:
        return bool(self.next_attempt and self.next_attempt > datetime.now(timezone.utc))

    @property
    def can_sync(self) -> bool:
        agora = datetime.now(timezone.utc)
        if self.next_attempt and self.next_attempt > agora:
            return False
        if self.pause_until and self.pause_until > agora:
            return False
        return self.database_ready

    def local_time(self, value: datetime | None) -> str:
        if value is None:
            return "Sem registro"
        return value.astimezone().strftime("%d/%m/%Y %H:%M")

    @property
    def updated_label(self) -> str:
        return self.local_time(self.updated_at)

    @property
    def next_attempt_label(self) -> str:
        return self.local_time(self.next_attempt)

    @property
    def pause_until_label(self) -> str:
        return self.local_time(self.pause_until)


def _utc_sqlite(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_web_status(
    database_path: Path,
    cnpj: str,
    *,
    password: str | None = None,
) -> WebStatus:
    caminho = Path(database_path).expanduser()
    if not caminho.is_file():
        return WebStatus(False, None, None, None, None, None, None, None)

    conexao = abrir_banco(caminho, password, somente_leitura=True)
    try:
        try:
            estado = conexao.execute(
                "SELECT ult_nsu, max_nsu, atualizado_em "
                "FROM estado_distribuicao WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            estado = None

        try:
            controle = conexao.execute(
                "SELECT ultima_tentativa_em, proxima_tentativa_em "
                "FROM controle_sincronizacao WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            controle = None

        try:
            pausa = conexao.execute(
                "SELECT ate_utc, motivo FROM pausa_distribuicao WHERE cnpj = ?",
                (cnpj,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            pausa = None
    finally:
        conexao.close()

    return WebStatus(
        database_ready=True,
        updated_at=_utc_sqlite(estado[2]) if estado else None,
        ult_nsu=estado[0] if estado else None,
        max_nsu=estado[1] if estado else None,
        last_attempt=_iso(controle[0]) if controle else None,
        next_attempt=_iso(controle[1]) if controle else None,
        pause_until=_iso(pausa[0]) if pausa else None,
        pause_reason=pausa[1] if pausa else None,
    )
