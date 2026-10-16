"""Log de auditoria sem conteúdo fiscal sensível."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

from nfe_consulta.web.log_retention import prune_sync_logs

from fastapi import Request

from nfe_consulta.web.auth import WebUser


class RetainedAuditHandler(RotatingFileHandler):
    """Rotação por tamanho e limpeza diária somente das ações SEFAZ."""

    def __init__(self, caminho: Path):
        super().__init__(caminho, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        self._cleanup_date = None
        self._cleanup()

    def _cleanup(self):
        today = datetime.now(timezone.utc).date()
        if self._cleanup_date == today:
            return
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        try:
            prune_sync_logs(Path(self.baseFilename), now=datetime.now(timezone.utc))
            self._cleanup_date = today
        except (OSError, UnicodeError):
            logging.getLogger(__name__).warning("Não foi possível limpar o histórico de sincronização.")
            self._cleanup_date = today
        finally:
            self.stream = self._open()

    def emit(self, record):
        self._cleanup()
        super().emit(record)


class AuditLog:
    def __init__(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"nfe.web.audit.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        handler = RetainedAuditHandler(caminho)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self._logger.addHandler(handler)

    def _write_payload(self, payload: dict) -> None:
        self._logger.info(
            json.dumps({**payload, "logged_at_utc": datetime.now(timezone.utc).isoformat()},
                       ensure_ascii=False, separators=(",", ":"))
        )

    def write(
        self,
        request: Request,
        user: WebUser,
        action: str,
        result: str,
        **details,
    ) -> None:
        self._write_payload(
            {
                "user": user.username,
                "admin": user.is_admin,
                "role": "admin" if user.is_admin else user.role,
                "action": action,
                "result": result,
                "client": request.client.host if request.client else None,
                **details,
            }
        )

    def write_system(
        self,
        action: str,
        result: str,
        **details,
    ) -> None:
        self._write_payload(
            {
                "user": "system",
                "admin": False,
                "action": action,
                "result": result,
                "client": None,
                **details,
            }
        )
