from pathlib import Path
from types import SimpleNamespace
import smtplib

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import Manifestacao, RetornoDistribuicao
from nfe_consulta.web import email_alerts
from nfe_consulta.web import sync_runtime


def retorno(codigo="210240"):
    evento = Manifestacao(codigo, "Operação não Realizada", "2026-09-28T12:00:00", "123", "1")
    return RetornoDistribuicao(138, "ok", "1", "1", (("3" * 44, evento),))


def test_apenas_evento_novo_gera_um_aviso_por_destinatario(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "eventos.db"))
    try:
        assert banco.salvar_retorno("123", retorno(), ("a@empresa.com.br", "b@empresa.com.br")) == 1
        assert banco.salvar_retorno("123", retorno(), ("a@empresa.com.br",)) == 0
        assert len(banco.notificacoes_pendentes()) == 2
        assert banco.obter_estado("123") == ("1", "1")
    finally:
        banco.fechar()


def test_sem_destinatarios_ou_outro_evento_nao_gera_aviso(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "eventos.db"))
    try:
        banco.salvar_retorno("123", retorno("210220"), ("a@empresa.com.br",))
        assert banco.notificacoes_pendentes() == []
    finally:
        banco.fechar()


def test_destinatarios_validacao_e_persistencia(tmp_path):
    arquivo = tmp_path / "secrets" / "email-recipients.json"
    assert email_alerts.salvar_destinatarios(arquivo, "A@Empresa.com.br, b@empresa.com.br\na@empresa.com.br") == (
        "a@empresa.com.br", "b@empresa.com.br"
    )
    assert email_alerts.carregar_destinatarios(arquivo) == (
        "a@empresa.com.br", "b@empresa.com.br"
    )
    with pytest.raises(ValueError):
        email_alerts.salvar_destinatarios(arquivo, "a@empresa.com.br\r\nBcc:outro@empresa.com.br")


def test_falha_smtp_mantem_fila_e_retentativa_entrega(monkeypatch, tmp_path):
    caminho = tmp_path / "eventos.db"
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno("123", retorno(), ("a@empresa.com.br",))
    banco.fechar()
    destinatarios = tmp_path / "email-recipients.json"
    email_alerts.salvar_destinatarios(destinatarios, "a@empresa.com.br")
    settings = SimpleNamespace(
        smtp_host="smtp.empresa.com.br", smtp_from="app@empresa.com.br",
        smtp_user="", smtp_password_file=Path("nao-usado"),
        email_recipients_file=destinatarios,
        current_database_password=lambda: None,
    )
    monkeypatch.setattr("nfe_consulta.web.sync_runtime.caminho_banco_configurado", lambda _: caminho)
    eventos = []
    audit = SimpleNamespace(write_system=lambda *a, **kw: eventos.append((a, kw)))
    monkeypatch.setattr(email_alerts, "_enviar", lambda *args: (_ for _ in ()).throw(OSError("offline")))
    assert email_alerts.enviar_pendentes(settings, audit) == 0
    banco = BancoManifestacoes(str(caminho))
    assert banco.contar_notificacoes_pendentes() == 1
    banco.fechar()
    enviados = []
    monkeypatch.setattr(email_alerts, "_enviar", lambda *args: enviados.append(args[1]))
    assert email_alerts.enviar_pendentes(settings, audit) == 1
    assert email_alerts.enviar_pendentes(settings, audit) == 0
    assert enviados == ["a@empresa.com.br"]
    banco = BancoManifestacoes(str(caminho))
    assert banco.contar_notificacoes_pendentes() == 0
    banco.fechar()


def test_sincronizacao_parcial_tenta_entregar_fila_no_finally(monkeypatch, tmp_path):
    caminho = tmp_path / "eventos.db"
    caminho.touch()
    arquivo = tmp_path / "recipients.json"
    email_alerts.salvar_destinatarios(arquivo, "fiscal@empresa.com.br")
    settings = SimpleNamespace(
        database_path=caminho, database_path_file=tmp_path / "db-path.txt",
        certificate_path_file=tmp_path / "cert-path.txt",
        certificate_password_file=tmp_path / "cert-password.txt",
        certificate_thumbprint=None, certificate_store="CurrentUser",
        sync_cooldown_minutes=120, email_recipients_file=arquivo,
        current_database_password=lambda: None,
    )
    chamadas = []

    def falha(parametros):
        chamadas.append(parametros.destinatarios_alerta)
        raise RuntimeError("falha após lote gravado")

    monkeypatch.setattr(sync_runtime, "sincronizar_banco", falha)
    monkeypatch.setattr(sync_runtime, "enviar_pendentes", lambda *args: chamadas.append("entrega"))
    with pytest.raises(RuntimeError):
        sync_runtime.sincronizar_configurado(settings, audit=object())
    assert chamadas == [("fiscal@empresa.com.br",), "entrega"]


def test_remover_destinatario_cancela_fila_sem_enviar(monkeypatch, tmp_path):
    caminho = tmp_path / "eventos.db"
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno("123", retorno(), ("antigo@empresa.com.br", "ativo@empresa.com.br"))
    banco.fechar()
    arquivo = tmp_path / "recipients.json"
    email_alerts.salvar_destinatarios(arquivo, "ativo@empresa.com.br")
    settings = SimpleNamespace(
        smtp_host="smtp", smtp_from="app@empresa.com.br", smtp_user="",
        smtp_password_file=tmp_path / "smtp.txt", email_recipients_file=arquivo,
        current_database_password=lambda: None,
    )
    monkeypatch.setattr(sync_runtime, "caminho_banco_configurado", lambda _: caminho)
    enviados = []
    monkeypatch.setattr(email_alerts, "_enviar", lambda _, email, *args: enviados.append(email))
    audit = SimpleNamespace(write_system=lambda *args, **kwargs: None)
    assert email_alerts.enviar_pendentes(settings, audit) == 1
    assert enviados == ["ativo@empresa.com.br"]
    banco = BancoManifestacoes(str(caminho))
    assert banco.contar_notificacoes_pendentes() == 0
    banco.fechar()


def test_destinatario_rejeitado_nao_bloqueia_os_demais(monkeypatch, tmp_path):
    caminho = tmp_path / "eventos.db"
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno("123", retorno(), ("ruim@empresa.com.br", "bom@empresa.com.br"))
    banco.fechar()
    arquivo = tmp_path / "recipients.json"
    email_alerts.salvar_destinatarios(arquivo, "ruim@empresa.com.br\nbom@empresa.com.br")
    settings = SimpleNamespace(
        smtp_host="smtp", smtp_from="app@empresa.com.br", smtp_user="",
        smtp_password_file=tmp_path / "smtp.txt", email_recipients_file=arquivo,
        current_database_password=lambda: None,
    )
    monkeypatch.setattr(sync_runtime, "caminho_banco_configurado", lambda _: caminho)
    enviados = []

    def enviar(_, email, *args):
        if email.startswith("ruim"):
            raise smtplib.SMTPRecipientsRefused({email: (550, b"unknown")})
        enviados.append(email)

    monkeypatch.setattr(email_alerts, "_enviar", enviar)
    audit = SimpleNamespace(write_system=lambda *args, **kwargs: None)
    assert email_alerts.enviar_pendentes(settings, audit) == 1
    assert enviados == ["bom@empresa.com.br"]
    banco = BancoManifestacoes(str(caminho))
    assert banco.contar_notificacoes_pendentes() == 0
    banco.fechar()


def test_arquivo_de_email_invalido_nao_interrompe_consulta_sefaz(monkeypatch, tmp_path):
    caminho = tmp_path / "eventos.db"
    caminho.touch()
    arquivo = tmp_path / "recipients.json"
    arquivo.write_text("{inválido", encoding="utf-8")
    settings = SimpleNamespace(
        database_path=caminho, database_path_file=tmp_path / "db-path.txt",
        certificate_path_file=tmp_path / "cert-path.txt",
        certificate_password_file=tmp_path / "cert-password.txt",
        certificate_thumbprint=None, certificate_store="CurrentUser",
        sync_cooldown_minutes=120, email_recipients_file=arquivo,
        current_database_password=lambda: None,
    )
    chamados = []
    monkeypatch.setattr(sync_runtime, "sincronizar_banco", lambda params: chamados.append(params.destinatarios_alerta))
    monkeypatch.setattr(sync_runtime, "enviar_pendentes", lambda *args: None)
    audit = SimpleNamespace(write_system=lambda *args, **kwargs: None)
    sync_runtime.sincronizar_configurado(settings, audit=audit)
    assert chamados == [()]
