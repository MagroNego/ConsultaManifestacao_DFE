"""Sincronização SEFAZ usando a configuração ativa do servidor Web."""

from __future__ import annotations

import os
import socket
from uuid import uuid4

from nfe_consulta.banco_config import carregar_caminho_banco
from nfe_consulta.certificado_config import carregar_config_certificado_arquivo
from nfe_consulta.config import CNPJ_PADRAO, UF_PADRAO
from nfe_consulta.servico import (
    ParametrosSincronizacao,
    sincronizar_banco,
)
from nfe_consulta.web.settings import WebSettings
from nfe_consulta.web.email_alerts import carregar_destinatarios, enviar_pendentes


def caminho_banco_configurado(settings: WebSettings):
    return carregar_caminho_banco(
        settings.database_path,
        path_file=settings.database_path_file,
    )


def sincronizar_configurado(settings: WebSettings, *, max_lotes: int = 50, audit=None):
    """Executa a mesma sincronização usada pela área administrativa."""
    banco = caminho_banco_configurado(settings)
    if not banco.is_file():
        raise FileNotFoundError(f"Banco configurado não encontrado: {banco}")

    cert_arquivo = carregar_config_certificado_arquivo(
        settings.certificate_path_file,
        settings.certificate_password_file,
    )

    try:
        destinatarios = carregar_destinatarios(settings.email_recipients_file)
    except (ValueError, OSError) as exc:
        destinatarios = ()
        if audit is not None:
            audit.write_system("email_alert", "erro", reason=type(exc).__name__)
    execucao = uuid4().hex
    diagnosticar = False
    if audit is not None:
        from nfe_consulta.web.status_view import read_web_status
        status = read_web_status(banco, CNPJ_PADRAO, password=settings.current_database_password())
        diagnosticar = status.can_sync
        if diagnosticar:
            audit.write_system("sefaz_sync_diagnostico", "iniciado", execucao=execucao,
                pid=os.getpid(), host=socket.gethostname(), banco=str(banco.resolve()),
                codigo=__file__, ult_nsu=status.ult_nsu, max_nsu=status.max_nsu)

    def progresso(lotes, ult_nsu, max_nsu, eventos):
        if audit is not None and diagnosticar:
            audit.write_system("sefaz_sync_diagnostico", "lote_gravado", execucao=execucao,
                lote=lotes, ult_nsu=ult_nsu, max_nsu=max_nsu)

    try:
        resumo = sincronizar_banco(
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
            destinatarios_alerta=destinatarios,
            ),
            progresso_sincronizacao=progresso,
        )
        if audit is not None and diagnosticar:
            audit.write_system("sefaz_sync_diagnostico", "concluido", execucao=execucao,
                somente_recuperacao=getattr(resumo, "somente_recuperacao", False),
                ult_nsu=getattr(resumo, "ult_nsu", None), max_nsu=getattr(resumo, "max_nsu", None),
                documentos_recuperados=getattr(resumo, "documentos_recuperados", None))
        return resumo
    except Exception as exc:
        if audit is not None and diagnosticar:
            audit.write_system("sefaz_sync_diagnostico", "erro", execucao=execucao,
                reason=type(exc).__name__, nsu_sefaz=getattr(exc, "ult_nsu", None))
        raise
    finally:
        # Também envia lotes já gravados quando um 656 interrompe a sincronização.
        if audit is not None:
            try:
                enviar_pendentes(settings, audit)
            except Exception as exc:
                audit.write_system("email_alert", "erro", reason=type(exc).__name__)
