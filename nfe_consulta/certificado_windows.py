import json
import os
import subprocess

from nfe_consulta.modelos import CertificadoWindows, NfeErroCertificado


STORES_PERMITIDOS = {"CurrentUser", "LocalMachine"}


def normalizar_store(store: str | None = None) -> str:
    valor = (store or os.getenv("NFE_CERT_STORE", "CurrentUser")).strip()
    if valor not in STORES_PERMITIDOS:
        raise NfeErroCertificado(
            "Repositório de certificado inválido. Use CurrentUser ou LocalMachine."
        )
    return valor


def listar_certificados_cliente(store: str | None = None) -> list[CertificadoWindows]:
    store = normalizar_store(store)
    script = rf'''
    $certs = Get-ChildItem -Path Cert:\{store}\My |
        Where-Object {{ $_.HasPrivateKey -eq $true }}
    $result = @()
    foreach ($cert in $certs) {{
        $cnpj = $null
        if ($cert.Subject -match '(?<!\d)(\d{{14}})(?!\d)') {{
            $cnpj = $Matches[1]
        }}
        $result += @{{
            thumbprint = $cert.Thumbprint
            subject    = $cert.Subject
            issuer     = $cert.Issuer
            valid_to   = $cert.NotAfter.ToString("yyyy-MM-dd")
            cnpj       = $cnpj
            store      = "{store}"
        }}
    }}
    $result | ConvertTo-Json -Compress -Depth 2
    '''
    try:
        proc = subprocess.run(
            [_powershell_executavel(), "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=True,
        )
        if not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]
        return [CertificadoWindows(**c) for c in data]
    except FileNotFoundError as exc:
        raise NfeErroCertificado(
            "PowerShell não encontrado. Este aplicativo deve ser executado no Windows."
        ) from exc
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise NfeErroCertificado(f"Falha ao ler certificados do Windows: {exc}") from exc


def _powershell_executavel() -> str:
    return "powershell.exe" if os.name == "nt" else "powershell"


def selecionar_certificado(
    certs: list[CertificadoWindows],
    indice: int = 0,
) -> CertificadoWindows:
    if not certs:
        raise NfeErroCertificado("Nenhum certificado com chave privada encontrado.")
    if indice < 0 or indice >= len(certs):
        raise NfeErroCertificado(f"Índice de certificado inválido: {indice}")
    return certs[indice]
