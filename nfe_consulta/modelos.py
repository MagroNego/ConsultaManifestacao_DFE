from dataclasses import dataclass
from typing import Optional


class NfeConsultaErro(Exception):
    pass


class NfeChaveInvalidaErro(NfeConsultaErro):
    pass


class NfeErroComunicacao(NfeConsultaErro):
    pass


class NfeErroCertificado(NfeConsultaErro):
    pass


class NfeErroResposta(NfeConsultaErro):
    pass


class NfeConsumoIndevidoErro(NfeErroComunicacao):
    pass


class NfeLimiteConsultaErro(NfeConsultaErro):
    pass


@dataclass(frozen=True)
class Manifestacao:
    codigo: str
    descricao: str
    data: str
    protocolo: str
    nsu: str = ""
    schema: str = ""


@dataclass(frozen=True)
class ResultadoConsulta:
    chave: str
    status_codigo: int
    status_motivo: str
    protocolo_nfe: Optional[str]
    manifestacoes: tuple  # tuple[Manifestacao, ...]
    erro: Optional[str] = None


@dataclass(frozen=True)
class CertificadoWindows:
    thumbprint: str
    subject: str
    issuer: str
    valid_to: str
    cnpj: Optional[str] = None
    store: str = "CurrentUser"


@dataclass(frozen=True)
class RetornoDistribuicao:
    status_codigo: int
    status_motivo: str
    ult_nsu: str
    max_nsu: str
    manifestacoes: tuple  # tuple[tuple[str, Manifestacao], ...]
    documentos_ignorados: int = 0
