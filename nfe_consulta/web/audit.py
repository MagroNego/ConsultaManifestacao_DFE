"""Log de auditoria sem conteúdo fiscal sensível."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Request

from nfe_consulta.web.auth import WebUser


class AuditLog:
    def __init__(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"nfe.web.audit.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        handler = RotatingFileHandler(
            caminho,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self._logger.addHandler(handler)

    def _write_payload(self, payload: dict) -> None:
        self._logger.info(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
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
