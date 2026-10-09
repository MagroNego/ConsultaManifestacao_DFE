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


def test_historico_distingue_sincronizacao_parcial(tmp_path):
    path = tmp_path / "web_audit.log"
    path.write_text(
        '2026-09-28 11:00:00 {"action":"sefaz_sync","result":"ok","completo":false,"lotes":50}\n',
        encoding="utf-8",
    )
    item = read_sync_history(path)[0]
    assert item.result == "Parcial"
    assert "lotes" in item.detail

def test_historico_separa_origens_e_nao_inventa_contagem_antiga(tmp_path):
    path=tmp_path/'web_audit.log'
    novo={'action':'sefaz_sync','result':'ok','eventos_novos':4,'documentos_atuais':12,'manifestacoes_atuais':3,'documentos_recuperados':10,'manifestacoes_recuperadas':1}
    antigo={'action':'sefaz_sync','result':'ok','eventos_novos':8}
    path.write_text('2026-10-09 12:00:00 '+json.dumps(antigo)+'\n2026-10-09 13:00:00 '+json.dumps(novo)+'\n')
    items=read_sync_history(path)
    assert items[0].result=='Execução concluída'
    assert (items[0].current_documents,items[0].current_events)==(12,3)
    assert (items[0].recovered_documents,items[0].recovered_events)==(10,1)
    assert items[1].current_documents is None
    assert items[1].recovered_events is None


def test_historico_identifica_execucao_somente_recuperacao(tmp_path):
    path = tmp_path / 'web_audit.log'
    path.write_text('2026-10-09 16:50:00 '+json.dumps({
        'action':'sefaz_sync_auto','result':'ok','completo':False,
        'somente_recuperacao':True,'documentos_recuperados':20})+'\n')
    item = read_sync_history(path)[0]
    assert 'Recuperação de pendências' in item.detail
    assert item.recovered_documents == 20
