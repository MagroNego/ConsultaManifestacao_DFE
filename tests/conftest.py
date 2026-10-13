"""Relógio da política de horário determinístico para testes com SEFAZ simulada."""
from datetime import datetime

import pytest

from nfe_consulta import janela_consulta


@pytest.fixture(autouse=True)
def horario_comercial(monkeypatch):
    # Os testes específicos de janela sobrescrevem este relógio nos limites.
    monkeypatch.setattr(
        janela_consulta, "agora_brasilia",
        lambda: datetime(2026, 10, 13, 10, tzinfo=janela_consulta.BRASILIA),
    )
