import re

from nfe_consulta.modelos import NfeChaveInvalidaErro


def validar_chave(chave: str) -> str:
    chave_limpa = re.sub(r"\D", "", chave)
    if len(chave_limpa) != 44:
        raise NfeChaveInvalidaErro(
            "Chave invalida: esperado 44 digitos numericos"
        )
    return chave_limpa


def numero_e_serie(chave: str) -> tuple[str, str]:
    """Campos nNF (9 digitos) e serie (3 digitos) da chave NF-e modelo 55."""
    if len(chave) != 44 or not chave.isdigit():
        return "", ""
    return str(int(chave[25:34])), chave[22:25]


def validar_cnpj(cnpj: str) -> str:
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    if len(cnpj_limpo) != 14:
        raise ValueError("CNPJ invalido: esperado 14 digitos")
    return cnpj_limpo


UFS = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15",
    "AP": "16", "TO": "17", "MA": "21", "PI": "22", "CE": "23",
    "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28",
    "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35",
    "PR": "41", "SC": "42", "RS": "43", "MS": "50", "MT": "51",
    "GO": "52", "DF": "53",
}


def validar_uf(uf: str) -> str:
    valor = uf.strip().upper()
    if valor in UFS:
        return UFS[valor]
    if valor in UFS.values():
        return valor
    raise ValueError("UF invalida: informe a sigla (ex.: RJ) ou o codigo IBGE")
