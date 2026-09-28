import base64
import gzip
import io
from xml.etree import ElementTree as StdET
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from nfe_consulta.modelos import (
    Manifestacao,
    NfeErroResposta,
    RetornoDistribuicao,
)
from nfe_consulta.parser import DESCRICOES

MAX_SOAP_BYTES = 32 * 1024 * 1024
MAX_DOCZIP_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024


def _nome_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _primeiro_texto(root: StdET.Element, *nomes: str) -> str:
    for nome in nomes:
        for elemento in root.iter():
            if _nome_local(elemento.tag) == nome and elemento.text:
                return elemento.text.strip()
    return ""


def _encontrar_retorno(root: StdET.Element) -> StdET.Element:
    if _nome_local(root.tag) == "retDistDFeInt":
        return root
    for elemento in root.iter():
        if _nome_local(elemento.tag) == "retDistDFeInt":
            return elemento
        if elemento.text and "<retDistDFeInt" in elemento.text:
            try:
                return ET.fromstring(elemento.text)
            except (StdET.ParseError, DefusedXmlException):
                pass
    raise NfeErroResposta("Resposta da SEFAZ sem retDistDFeInt")


def parse_documento_distribuido(
    xml_bytes: bytes, nsu: str = "", schema: str = ""
) -> tuple[str, Manifestacao] | None:
    if len(xml_bytes) > MAX_XML_BYTES:
        raise NfeErroResposta(f"XML distribuido excede limite de tamanho no NSU {nsu}")
    try:
        root = ET.fromstring(xml_bytes)
    except (StdET.ParseError, DefusedXmlException) as exc:
        raise NfeErroResposta(f"XML distribuido invalido no NSU {nsu}: {exc}") from exc

    if _nome_local(root.tag) not in ("resEvento", "procEventoNFe"):
        return None
    codigo = _primeiro_texto(root, "tpEvento")
    if codigo not in DESCRICOES:
        return None

    chave = _primeiro_texto(root, "chNFe")
    if len(chave) != 44 or not chave.isdigit():
        raise NfeErroResposta(f"Evento do NSU {nsu} sem chave NF-e valida")

    manifestacao = Manifestacao(
        codigo=codigo,
        descricao=DESCRICOES[codigo],
        data=_primeiro_texto(root, "dhRegEvento", "dhEvento"),
        protocolo=_primeiro_texto(root, "nProt"),
        nsu=nsu,
        schema=schema,
    )
    return chave, manifestacao


def parse_retorno_distribuicao(xml_str: str) -> RetornoDistribuicao:
    if len(xml_str.encode("utf-8")) > MAX_SOAP_BYTES:
        raise NfeErroResposta("Resposta da SEFAZ excede limite de tamanho")
    try:
        envelope = ET.fromstring(xml_str)
    except (StdET.ParseError, DefusedXmlException) as exc:
        raise NfeErroResposta(f"Resposta XML invalida da SEFAZ: {exc}") from exc

    root = _encontrar_retorno(envelope)
    status_texto = _primeiro_texto(root, "cStat") or "0"
    try:
        status = int(status_texto)
    except ValueError as exc:
        raise NfeErroResposta(f"cStat invalido na resposta: {status_texto}") from exc

    manifestacoes = []
    ignorados = 0
    for doc_zip in root.iter():
        if _nome_local(doc_zip.tag) != "docZip":
            continue
        if ignorados + len(manifestacoes) >= 50:
            raise NfeErroResposta("Resposta da SEFAZ com mais de 50 documentos")
        nsu = doc_zip.attrib.get("NSU", "")
        schema = doc_zip.attrib.get("schema", "")
        try:
            texto_base64 = "".join((doc_zip.text or "").split())
            if len(texto_base64) > ((MAX_DOCZIP_BYTES + 2) // 3) * 4 + 4:
                raise NfeErroResposta(f"docZip excede limite de tamanho no NSU {nsu}")
            compactado = base64.b64decode(texto_base64, validate=True)
            with gzip.GzipFile(fileobj=io.BytesIO(compactado)) as fonte:
                xml_documento = fonte.read(MAX_XML_BYTES + 1)
            if len(xml_documento) > MAX_XML_BYTES:
                raise NfeErroResposta(f"XML expandido excede limite no NSU {nsu}")
        except (ValueError, OSError) as exc:
            raise NfeErroResposta(f"docZip invalido no NSU {nsu}: {exc}") from exc

        evento = parse_documento_distribuido(xml_documento, nsu, schema)
        if evento is None:
            ignorados += 1
        else:
            manifestacoes.append(evento)

    ult_nsu = _primeiro_texto(root, "ultNSU")
    max_nsu = _primeiro_texto(root, "maxNSU")
    if status in (137, 138) and (not ult_nsu.isdigit() or not max_nsu.isdigit()):
        raise NfeErroResposta("Resposta sem ultNSU/maxNSU validos")
    return RetornoDistribuicao(
        status_codigo=status,
        status_motivo=_primeiro_texto(root, "xMotivo"),
        ult_nsu=(ult_nsu or "0").zfill(15),
        max_nsu=(max_nsu or "0").zfill(15),
        manifestacoes=tuple(manifestacoes),
        documentos_ignorados=ignorados,
        ult_nsu_informado=bool(ult_nsu and ult_nsu.isdigit()),
    )
