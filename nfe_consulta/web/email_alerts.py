"""Destinatários administrados na Web e entrega de avisos após a sincronização."""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import tempfile
import threading
from email.message import EmailMessage
from pathlib import Path

from nfe_consulta.banco import BancoManifestacoes


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_delivery_lock = threading.Lock()


def normalizar_destinatarios(texto: str) -> tuple[str, ...]:
    candidatos = re.split(r"[,;\s]+", texto.strip()) if texto.strip() else []
    if len(candidatos) > 20:
        raise ValueError("Cadastre no máximo 20 endereços.")
    emails = tuple(dict.fromkeys(item.lower() for item in candidatos))
    if any(len(item) > 254 or not EMAIL_PATTERN.fullmatch(item) or ".." in item for item in emails):
        raise ValueError("Informe endereços de e-mail válidos, separados por linha ou vírgula.")
    return emails


def carregar_destinatarios(arquivo: Path) -> tuple[str, ...]:
    if not arquivo.is_file():
        return ()
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if not isinstance(dados, list) or any(not isinstance(item, str) for item in dados):
        raise ValueError("Arquivo de destinatários inválido.")
    return normalizar_destinatarios("\n".join(dados))


def salvar_destinatarios(arquivo: Path, texto: str) -> tuple[str, ...]:
    emails = normalizar_destinatarios(texto)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".destinatarios-", dir=arquivo.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(emails, handle, ensure_ascii=False)
        os.replace(temporario, arquivo)
    finally:
        try:
            os.unlink(temporario)
        except FileNotFoundError:
            pass
    return emails


def smtp_pronto(settings) -> bool:
    return bool(
        settings.smtp_host and settings.smtp_from
        and (not settings.smtp_user or settings.smtp_password_file.is_file())
    )


def contar_pendentes(settings) -> int | None:
    from nfe_consulta.web.sync_runtime import caminho_banco_configurado

    caminho = caminho_banco_configurado(settings)
    if not caminho.is_file():
        return None
    banco = BancoManifestacoes(str(caminho), senha=settings.current_database_password())
    try:
        return banco.contar_notificacoes_pendentes()
    finally:
        banco.fechar()


def _enviar(settings, destinatario: str, chave: str, data: str, protocolo: str) -> None:
    mensagem = EmailMessage()
    mensagem["Subject"] = "NF-e: nova Operação não Realizada"
    mensagem["From"] = settings.smtp_from
    mensagem["To"] = destinatario
    mensagem.set_content(
        "Foi recebido um novo evento de Operação não Realizada (210240).\n\n"
        f"Chave NF-e: {chave}\nData do evento: {data}\nProtocolo: {protocolo}\n\n"
        "Confira o registro na Consulta de Manifestação."
    )
    if settings.smtp_security == "ssl":
        conexao = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=10,
            context=ssl.create_default_context(),
        )
    else:
        conexao = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    with conexao as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        senha = settings.smtp_password_file
        if settings.smtp_user:
            if not senha.is_file():
                raise RuntimeError("Senha SMTP ausente em secrets/smtp-password.txt.")
            smtp.login(settings.smtp_user, senha.read_text(encoding="utf-8").rstrip("\r\n"))
        smtp.send_message(mensagem)


def enviar_pendentes(settings, audit, *, limite: int = 100) -> int:
    """Tenta entregar avisos gravados; falha de e-mail nunca altera o cursor NSU."""
    if not smtp_pronto(settings):
        return 0
    if not _delivery_lock.acquire(blocking=False):
        return 0
    try:
        return _enviar_pendentes_sem_lock(settings, audit, limite=limite)
    finally:
        _delivery_lock.release()


def _enviar_pendentes_sem_lock(settings, audit, *, limite: int) -> int:
    from nfe_consulta.web.sync_runtime import caminho_banco_configurado

    caminho = caminho_banco_configurado(settings)
    if not caminho.is_file():
        return 0
    banco = BancoManifestacoes(str(caminho), senha=settings.current_database_password())
    enviados = 0
    try:
        for id_, destinatario, chave, data, protocolo in banco.notificacoes_pendentes(limite):
            try:
                _enviar(settings, destinatario, chave, data, protocolo)
            except Exception as exc:
                # O log não inclui endereço nem conteúdo fiscal.
                banco.registrar_envio_email(id_, type(exc).__name__)
                audit.write_system("email_alert", "erro", reason=type(exc).__name__)
                break  # Evita insistir no servidor SMTP indisponível.
            else:
                banco.registrar_envio_email(id_)
                enviados += 1
                audit.write_system("email_alert", "enviado")
    finally:
        banco.fechar()
    return enviados
