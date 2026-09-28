import json
import os
import subprocess
from xml.sax.saxutils import escape

from nfe_consulta.certificado_windows import _powershell_executavel
from nfe_consulta.modelos import (
    CertificadoWindows,
    NfeConsumoIndevidoErro,
    NfeErroCertificado,
    NfeErroComunicacao,
    RetornoDistribuicao,
)
from nfe_consulta.parser_distribuicao import parse_retorno_distribuicao


ENDPOINT_PRODUCAO = (
    "https://www1.nfe.fazenda.gov.br/"
    "NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
)
SOAP_ACTION = (
    "http://www.portalfiscal.inf.br/nfe/wsdl/"
    "NFeDistribuicaoDFe/nfeDistDFeInteresse"
)


def _motivo_exibivel(motivo: str) -> str:
    """Limita texto remoto e remove controles de terminal antes de exibir e salvar."""
    return " ".join("".join(
        " " if caractere.isspace() else caractere
        for caractere in motivo if caractere.isspace() or caractere.isprintable()
    ).split())[:400]


def _erro_consumo_indevido(
    retorno: RetornoDistribuicao, *, ult_nsu_enviado: str | None = None
) -> NfeConsumoIndevidoErro:
    motivo = _motivo_exibivel(retorno.status_motivo) or "Consumo Indevido (sem xMotivo na resposta)"
    diagnostico = ""
    if ult_nsu_enviado is not None:
        diagnostico = f" | ultNSU enviado: {ult_nsu_enviado.zfill(15)}"
        if retorno.ult_nsu_informado:
            diagnostico += f" | ultNSU informado pela SEFAZ: {retorno.ult_nsu}"
        else:
            diagnostico += " | ultNSU da SEFAZ: não informado na rejeição"
    return NfeConsumoIndevidoErro(
        f"SEFAZ retornou 656 | xMotivo: {motivo}{diagnostico} "
        "| Aguarde uma hora antes de tentar novamente."
    )


def montar_dist_nsu(cnpj: str, c_uf_autor: str, ult_nsu: str) -> str:
    return (
        '<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
        "<tpAmb>1</tpAmb>"
        f"<cUFAutor>{escape(c_uf_autor)}</cUFAutor>"
        f"<CNPJ>{escape(cnpj)}</CNPJ>"
        f"<distNSU><ultNSU>{escape(ult_nsu.zfill(15))}</ultNSU></distNSU>"
        "</distDFeInt>"
    )


def montar_cons_chave(cnpj: str, c_uf_autor: str, chave: str) -> str:
    return (
        '<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
        "<tpAmb>1</tpAmb>"
        f"<cUFAutor>{escape(c_uf_autor)}</cUFAutor>"
        f"<CNPJ>{escape(cnpj)}</CNPJ>"
        f"<consChNFe><chNFe>{escape(chave)}</chNFe></consChNFe>"
        "</distDFeInt>"
    )


def montar_soap(dist_dfe: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>{dist_dfe}</nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>'''


def _enviar_soap_windows(
    soap: str,
    certificado: CertificadoWindows,
    endpoint: str = ENDPOINT_PRODUCAO,
) -> str:
    payload = json.dumps(
        {
            "url": endpoint,
            "soap": soap,
            "thumbprint": certificado.thumbprint,
            "store": certificado.store,
            "path": certificado.file_path,
            "password": certificado.file_password,
            "action": SOAP_ACTION,
        }
    )
    ps_script = r'''
$ErrorActionPreference = "Stop"
$null = Add-Type -AssemblyName System.Net.Http
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$cert = $null
$certFromFile = $false
if ($payload.path) {
    $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(
        $payload.path,
        $payload.password,
        $flags
    )
    $certFromFile = $true
} else {
    $store = if ($payload.store -eq "LocalMachine") { "LocalMachine" } else { "CurrentUser" }
    $cert = Get-Item ("Cert:\" + $store + "\My\" + $payload.thumbprint) -ErrorAction Stop
}
if (-not $cert.HasPrivateKey) { throw "Certificado sem chave privada" }

$handler = $null
$client = $null
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    $handler = New-Object System.Net.Http.HttpClientHandler
    [void]$handler.ClientCertificates.Add($cert)
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [System.TimeSpan]::FromSeconds(60)
    $client.MaxResponseContentBufferSize = 33554432

    $content = New-Object System.Net.Http.StringContent(
        $payload.soap, [System.Text.Encoding]::UTF8
    )
    $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse(
        'application/soap+xml; charset=utf-8; action="' + $payload.action + '"'
    )
    $response = $client.PostAsync($payload.url, $content).GetAwaiter().GetResult()
    $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if (-not $response.IsSuccessStatusCode) {
        throw ("HTTP " + [int]$response.StatusCode + " retornado pelo Ambiente Nacional")
    }
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::Out.Write($body)
} finally {
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
    if ($certFromFile -and $cert) { $cert.Dispose() }
}
'''
    try:
        proc = subprocess.run(
            [_powershell_executavel(), "-NoProfile", "-Command", ps_script],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        raise NfeErroCertificado(
            "PowerShell nao encontrado. Execute o aplicativo no Windows."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise NfeErroComunicacao("Timeout ao conectar com a SEFAZ") from exc

    if proc.returncode != 0:
        detalhe = (proc.stderr.strip() or f"PowerShell encerrou com codigo {proc.returncode}")[:500]
        if "certificado" in detalhe.lower():
            raise NfeErroCertificado(detalhe)
        raise NfeErroComunicacao(detalhe)
    if not proc.stdout.strip():
        raise NfeErroComunicacao("Resposta vazia da SEFAZ")
    return proc.stdout.strip()


def consultar_distribuicao(
    cnpj: str,
    c_uf_autor: str,
    ult_nsu: str,
    certificado: CertificadoWindows,
) -> RetornoDistribuicao:
    dist_dfe = montar_dist_nsu(cnpj, c_uf_autor, ult_nsu)
    resposta = _enviar_soap_windows(montar_soap(dist_dfe), certificado)
    retorno = parse_retorno_distribuicao(resposta)
    if retorno.status_codigo == 656:
        raise _erro_consumo_indevido(retorno, ult_nsu_enviado=ult_nsu)
    if retorno.status_codigo not in (137, 138):
        raise NfeErroComunicacao(
            f"SEFAZ retornou {retorno.status_codigo}: {retorno.status_motivo}"
        )
    return retorno


def consultar_por_chave(
    cnpj: str,
    c_uf_autor: str,
    chave: str,
    certificado: CertificadoWindows,
) -> RetornoDistribuicao:
    consulta = montar_cons_chave(cnpj, c_uf_autor, chave)
    resposta = _enviar_soap_windows(montar_soap(consulta), certificado)
    retorno = parse_retorno_distribuicao(resposta)
    if retorno.status_codigo == 656:
        raise _erro_consumo_indevido(retorno)
    if retorno.status_codigo not in (137, 138):
        raise NfeErroComunicacao(
            f"SEFAZ retornou {retorno.status_codigo}: {retorno.status_motivo}"
        )
    return retorno
