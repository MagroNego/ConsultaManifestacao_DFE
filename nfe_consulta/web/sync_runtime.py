"""Sincronização SEFAZ usando a configuração ativa do servidor Web."""

from __future__ import annotations

from nfe_consulta.banco_config import carregar_caminho_banco
from nfe_consulta.certificado_config import carregar_config_certificado_arquivo
from nfe_consulta.config import CNPJ_PADRAO, UF_PADRAO
from nfe_consulta.servico import (
    ParametrosSincronizacao,
    sincronizar_banco,
)
from nfe_consulta.web.settings import WebSettings


def caminho_banco_configurado(settings: WebSettings):
    return carregar_caminho_banco(
        settings.database_path,
        path_file=settings.database_path_file,
    )


def sincronizar_configurado(settings: WebSettings, *, max_lotes: int = 50):
    """Executa a mesma sincronização usada pela área administrativa."""
    banco = caminho_banco_configurado(settings)
    if not banco.is_file():
        raise FileNotFoundError(f"Banco configurado não encontrado: {banco}")

    cert_arquivo = carregar_config_certificado_arquivo(
        settings.certificate_path_file,
        settings.certificate_password_file,
    )

    return sincronizar_banco(
        ParametrosSincronizacao(
            banco=banco,
            cnpj=CNPJ_PADRAO,
            uf=UF_PADRAO,
            max_lotes=max_lotes,
            senha_banco=settings.current_database_password(),
            cert_thumbprint=(
                None if cert_arquivo is not None else settings.certificate_thumbprint
            ),
            cert_store=settings.certificate_store,
            cert_arquivo=cert_arquivo.path if cert_arquivo is not None else None,
            cert_senha_arquivo=(
                cert_arquivo.password if cert_arquivo is not None else None
            ),
            cooldown_minutos=settings.sync_cooldown_minutes,
        )
    )
