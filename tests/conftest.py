"""Relógio da política de horário determinístico para testes com SEFAZ simulada."""
from datetime import datetime, timedelta

import pytest

from nfe_consulta import janela_consulta


@pytest.fixture(autouse=True)
def horario_noturno(monkeypatch):
    agora = datetime.now(janela_consulta.BRASILIA)
    referencia = agora.replace(hour=1, minute=0, second=0, microsecond=0)
    if referencia > agora:
        referencia -= timedelta(days=1)
    # Mantém o relógio da política anterior às reservas feitas no banco real.
    # Os testes específicos de janela sobrescrevem este relógio nos limites.
    monkeypatch.setattr(
        janela_consulta, "agora_brasilia",
        lambda: referencia,
    )
