"""Leitura segura de certificado A1 PFX/P12 sem instalar no Windows."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from nfe_consulta.certificado_windows import _powershell_executavel
from nfe_consulta.modelos import CertificadoWindows, NfeErroCertificado


EXTENSOES_PERMITIDAS = {".pfx", ".p12"}


def carregar_certificado_arquivo(
    caminho: str | Path,
    senha: str | None,
) -> CertificadoWindows:
    arquivo = Path(caminho).expanduser().resolve()

    if not arquivo.is_file():
        raise NfeErroCertificado(f"Arquivo de certificado não encontrado: {arquivo}")
    if arquivo.suffix.lower() not in EXTENSOES_PERMITIDAS:
        raise NfeErroCertificado("Use um certificado A1 .pfx ou .p12.")

    payload = json.dumps(
        {
            "path": str(arquivo),
            "password": senha or "",
        }
    )

    script = r'''
$ErrorActionPreference = "Stop"
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(
    $payload.path,
    $payload.password,
    $flags
)
try {
    if (-not $cert.HasPrivateKey) { throw "Certificado sem chave privada." }
    $cnpj = $null
    if ($cert.Subject -match '(?<!\d)(\d{14})(?!\d)') {
        $cnpj = $Matches[1]
    }
    $result = @{
        thumbprint = $cert.Thumbprint
        subject    = $cert.Subject
        issuer     = $cert.Issuer
        valid_to   = $cert.NotAfter.ToString("yyyy-MM-dd")
        cnpj       = $cnpj
    }
    $result | ConvertTo-Json -Compress
} finally {
    $cert.Dispose()
}
'''

    try:
        proc = subprocess.run(
            [_powershell_executavel(), "-NoProfile", "-Command", script],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        raise NfeErroCertificado(
            "PowerShell não encontrado. Execute a aplicação no Windows."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise NfeErroCertificado("Timeout ao abrir o certificado A1.") from exc

    if proc.returncode != 0:
        detalhe = (proc.stderr.strip() or "Falha ao abrir o certificado.")[:500]
        raise NfeErroCertificado(
            "Não foi possível abrir o certificado. Verifique o arquivo e a senha. "
            f"Detalhe: {detalhe}"
        )

    try:
        dados = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise NfeErroCertificado("Resposta inválida ao ler o certificado.") from exc

    return CertificadoWindows(
        thumbprint=dados["thumbprint"],
        subject=dados["subject"],
        issuer=dados["issuer"],
        valid_to=dados["valid_to"],
        cnpj=dados.get("cnpj"),
        store="Arquivo",
        file_path=str(arquivo),
        file_password=senha or "",
    )
