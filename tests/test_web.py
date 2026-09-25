from types import SimpleNamespace

from fastapi.testclient import TestClient

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.web.app import create_app
from nfe_consulta.web.auth import WebUser, csrf_token
from nfe_consulta.web.settings import WebSettings


CHAVE = "33260812345678000199550010000917791147439711"


def settings_web(tmp_path, *, admin=False, auth_mode="dev", admin_users=frozenset()):
    return WebSettings(
        environment="development",
        auth_mode=auth_mode,
        user_header="X-NFE-User",
        name_header="X-NFE-Name",
        proxy_secret_header="X-NFE-Proxy-Secret",
        proxy_secret="segredo-de-proxy-com-tamanho-suficiente",
        admin_users=admin_users,
        dev_user="usuario@empresa.local",
        dev_name="Usuário Teste",
        dev_admin=admin,
        csrf_secret="c" * 64,
        database_path=tmp_path / "dados" / "historico.db",
        database_password=None,
        certificate_store="CurrentUser",
        certificate_thumbprint=None,
        bind_host="127.0.0.1",
        bind_port=8080,
        root_path="",
        forwarded_allow_ips="127.0.0.1",
        audit_log=tmp_path / "logs" / "web_audit.log",
        sync_cooldown_minutes=120,
    )


def criar_banco(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    banco = BancoManifestacoes(str(caminho))
    banco.fechar()


def test_usuario_comum_tem_excel_e_status_mas_nao_atualizar(tmp_path):
    cfg = settings_web(tmp_path, admin=False)
    app = create_app(cfg)

    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert ">Excel<" in home.text
        assert ">Status<" in home.text
        assert ">Atualizar<" not in home.text
        assert client.get("/status").status_code == 200
        assert client.get("/atualizar").status_code == 403


def test_admin_ve_as_tres_acoes(tmp_path):
    cfg = settings_web(tmp_path, admin=True)
    app = create_app(cfg)

    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert ">Excel<" in home.text
        assert ">Status<" in home.text
        assert ">Atualizar<" in home.text
        pagina = client.get("/atualizar")
        assert pagina.status_code == 200
        assert "Sincronizar com a SEFAZ" in pagina.text
        assert "2 horas" in pagina.text


def test_proxy_exige_segredo_e_aplica_allowlist_admin(tmp_path):
    cfg = settings_web(
        tmp_path,
        auth_mode="proxy",
        admin_users=frozenset({"admin@empresa.local"}),
    )
    app = create_app(cfg)

    with TestClient(app) as client:
        assert client.get("/").status_code == 401

        comum = {
            "X-NFE-Proxy-Secret": cfg.proxy_secret,
            "X-NFE-User": "comum@empresa.local",
        }
        assert client.get("/", headers=comum).status_code == 200
        assert client.get("/status", headers=comum).status_code == 200
        assert client.get("/atualizar", headers=comum).status_code == 403

        admin = {
            "X-NFE-Proxy-Secret": cfg.proxy_secret,
            "X-NFE-User": "ADMIN@empresa.local",
            "X-NFE-Name": "Administrador",
        }
        assert client.get("/atualizar", headers=admin).status_code == 200


def test_excel_web_gera_xlsx_com_banco_local(tmp_path):
    cfg = settings_web(tmp_path)
    criar_banco(cfg.database_path)
    app = create_app(cfg)
    user = WebUser(cfg.dev_user, cfg.dev_name, False)
    token = csrf_token(user, cfg)

    with TestClient(app) as client:
        resposta = client.post(
            "/excel",
            data={"csrf": token},
            files={
                "files": (
                    "CHAVES.txt",
                    CHAVE + "\n",
                    "text/plain",
                )
            },
        )

    assert resposta.status_code == 200
    assert resposta.content.startswith(b"PK")
    assert "spreadsheetml.sheet" in resposta.headers["content-type"]
    assert cfg.audit_log.is_file()


def test_excel_web_bloqueia_csrf_invalido(tmp_path):
    cfg = settings_web(tmp_path)
    criar_banco(cfg.database_path)
    app = create_app(cfg)

    with TestClient(app) as client:
        resposta = client.post(
            "/excel",
            data={"csrf": "invalido"},
            files={"files": ("CHAVES.txt", CHAVE + "\n", "text/plain")},
        )

    assert resposta.status_code == 403


def test_admin_pode_disparar_atualizacao_sefaz(tmp_path, monkeypatch):
    cfg = settings_web(tmp_path, admin=True)
    criar_banco(cfg.database_path)
    app = create_app(cfg)
    user = WebUser(cfg.dev_user, cfg.dev_name, True)
    token = csrf_token(user, cfg)

    chamadas = []

    def fake_sync(parametros):
        chamadas.append(parametros)
        return SimpleNamespace(
            lotes=1,
            eventos_novos=2,
            ult_nsu="10".zfill(15),
            max_nsu="10".zfill(15),
            completo=True,
            cache=False,
        )

    monkeypatch.setattr("nfe_consulta.web.app.sincronizar_banco", fake_sync)

    with TestClient(app) as client:
        resposta = client.post(
            "/atualizar/sincronizar",
            data={"csrf": token, "max_lotes": "25"},
            follow_redirects=False,
        )

    assert resposta.status_code == 303
    assert chamadas[0].max_lotes == 25
    assert chamadas[0].cooldown_minutos == 120


def test_status_mostra_ultima_gravacao_sem_chamar_sefaz(tmp_path):
    cfg = settings_web(tmp_path)
    criar_banco(cfg.database_path)
    app = create_app(cfg)

    with TestClient(app) as client:
        resposta = client.get("/status")

    assert resposta.status_code == 200
    assert "Última gravação" in resposta.text
    assert "Sem sincronização" in resposta.text


def test_headers_de_seguranca_e_healthcheck(tmp_path):
    cfg = settings_web(tmp_path)
    app = create_app(cfg)

    with TestClient(app) as client:
        health = client.get("/healthz")
        home = client.get("/")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert home.headers["x-frame-options"] == "DENY"
    assert home.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in home.headers["content-security-policy"]
