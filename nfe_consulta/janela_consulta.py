"""Janela de consultas externas; leitura do banco local permanece disponível."""
from datetime import datetime, time, timedelta, timezone

from nfe_consulta.modelos import NfeLimiteConsultaErro

BRASILIA = timezone(timedelta(hours=-3))


class NfeJanelaConsultaErro(NfeLimiteConsultaErro):
    pass


def agora_brasilia():
    return datetime.now(BRASILIA)


def proxima_abertura(instante=None):
    agora = instante if instante is not None else agora_brasilia()
    if agora.tzinfo is None:
        raise ValueError("O instante deve ter fuso horário")
    agora = agora.astimezone(BRASILIA)
    # A janela atravessa a meia-noite: 22:00 inclusive até 04:00 exclusiva.
    if agora.hour >= 22 or agora.hour < 4:
        return agora
    return datetime.combine(agora.date(), time(22), tzinfo=BRASILIA)


def exigir_janela():
    agora = agora_brasilia()
    if proxima_abertura(agora) > agora:
        raise NfeJanelaConsultaErro(
            "Consultas à SEFAZ permitidas das 22h às 04h (horário de Brasília). "
            "A consulta ao banco local continua disponível."
        )
