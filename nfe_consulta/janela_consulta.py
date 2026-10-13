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
    inicio = datetime.combine(agora.date(), time(8), tzinfo=BRASILIA)
    fim = inicio.replace(hour=18)
    if agora < inicio:
        return inicio
    if agora >= fim:
        return inicio + timedelta(days=1)
    return agora


def exigir_janela():
    agora = agora_brasilia()
    if proxima_abertura(agora) > agora:
        raise NfeJanelaConsultaErro(
            "Consultas à SEFAZ permitidas das 08h às 18h (horário de Brasília). "
            "A consulta ao banco local continua disponível."
        )
