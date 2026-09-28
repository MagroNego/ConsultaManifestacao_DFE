import json

from nfe_consulta.web.sync_history import read_sync_history


def test_historico_ler_rotacao_sem_expor_dados_internos(tmp_path):
    path = tmp_path / "web_audit.log"
    old = path.with_name(path.name + ".1")
    secret = "detalhe interno do servidor"

    def line(when, **payload):
        return f"{when} {json.dumps(payload)}\n"

    old.write_text(line("2026-09-27 08:00:00", action="sefaz_sync_auto", result="ok",
                        lotes=2, eventos_novos=0, user="system"), encoding="utf-8")
    path.write_text(
        line("2026-09-28 10:00:00", action="admin_login", result="ok", user="admin")
        + "linha inválida\n"
        + line("2026-09-28 11:00:00", action="sefaz_sync", result="erro",
               reason="NfeConsumoIndevidoErro", user="usuario-interno", client="10.0.0.1", detail=secret),
        encoding="utf-8",
    )
    items = read_sync_history(path)
    assert len(items) == 2
    assert items[0].result == "Falhou"
    assert "656" in items[0].detail
    assert items[0].origin == "Manual"
    assert secret not in repr(items)
    assert "10.0.0.1" not in repr(items)
    assert items[1].new_events == 0
    assert items[1].origin == "Automática"
    assert len(read_sync_history(path, limit=1)) == 1
