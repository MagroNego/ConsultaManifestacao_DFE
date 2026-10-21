from datetime import datetime, timezone
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
    items = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))
    assert len(items) == 2
    assert items[0].result == "Falhou"
    assert "656" in items[0].detail
    assert items[0].origin == "Manual"
    assert secret not in repr(items)
    assert "10.0.0.1" not in repr(items)
    assert items[1].new_events == 0
    assert items[1].origin == "Automática"
    assert len(read_sync_history(path, limit=1, now=datetime(2026, 10, 15, tzinfo=timezone.utc))) == 1


def test_historico_distingue_sincronizacao_parcial(tmp_path):
    path = tmp_path / "web_audit.log"
    path.write_text(
        '2026-09-28 11:00:00 {"action":"sefaz_sync","result":"ok","completo":false,"lotes":50}\n',
        encoding="utf-8",
    )
    item = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))[0]
    assert item.result == "Parcial"
    assert "lotes" in item.detail

def test_historico_separa_origens_e_nao_inventa_contagem_antiga(tmp_path):
    path=tmp_path/'web_audit.log'
    novo={'action':'sefaz_sync','result':'ok','eventos_novos':4,'documentos_atuais':12,'manifestacoes_atuais':3,'documentos_recuperados':10,'manifestacoes_recuperadas':1}
    antigo={'action':'sefaz_sync','result':'ok','eventos_novos':8}
    path.write_text('2026-10-09 12:00:00 '+json.dumps(antigo)+'\n2026-10-09 13:00:00 '+json.dumps(novo)+'\n')
    items=read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))
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
    item = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))[0]
    assert 'Recuperação de pendências' in item.detail
    assert item.recovered_documents == 20


def test_historico_omite_aviso_repetido_sem_remover_pausa_ou_alterar_log(tmp_path):
    path = tmp_path / 'audit.log'
    payload = {'action': 'sefaz_sync_auto', 'result': 'ignorado', 'reason': 'cooldown',
               'recuperacao_cons_nsu': False, 'eventos_novos': 0}
    original = '2026-10-21 03:00:00 ' + json.dumps(payload) + '\n'
    path.write_text(original)
    item = read_sync_history(path, now=datetime(2026, 10, 21, 7, tzinfo=timezone.utc))[0]
    assert item.detail == 'Intervalo entre consultas ainda ativo'
    assert item.new_events == 0
    assert item.current_documents is None
    assert item.when == '21/10/2026 03:00:00 (servidor)'
    assert path.read_text() == original


def test_agrupa_espera_e_conclusao_por_hora_sem_somar_ou_misturar_manual(tmp_path):
    path = tmp_path / 'audit.log'
    records = [
        {'action':'sefaz_sync_auto', 'result':'ignorado', 'reason':'cooldown', 'quando':'2026-10-21T02:00:00-03:00'},
        {'action':'sefaz_sync_auto', 'result':'ok', 'documentos_atuais':33, 'eventos_novos':8, 'logged_at_utc':'2026-10-21T05:01:54+00:00'},
        {'action':'sefaz_sync', 'result':'ok', 'eventos_novos':1, 'quando':'2026-10-21T02:05:00-03:00'},
    ]
    path.write_text(''.join('2026-10-21 05:00:00 '+json.dumps(p)+'\n' for p in records))
    items=read_sync_history(path, now=datetime(2026,10,21,8,tzinfo=timezone.utc))
    assert len(items)==2 and items[0].origin=='Manual'
    group=items[1]
    assert group.when=='21/10/2026 02h (Brasília)'
    assert group.result=='Execução concluída' and group.new_events==8 and group.current_documents==33
    assert [a.result for a in group.attempts]==['Não executada','Execução concluída']
    assert 'Intervalo' in group.attempts[0].detail


def test_agendamento_expresso_agrupa_retentativa_em_outra_hora_e_na_rotacao(tmp_path):
    path=tmp_path/'audit.log'
    slot='2026-10-20T22:30:00-03:00'
    older={'action':'sefaz_sync_auto','result':'ignorado','reason':'cooldown','scheduled_for':slot,'quando':'2026-10-20T22:30:00-03:00'}
    newer={'action':'sefaz_sync_auto','result':'ok','scheduled_for':slot,'quando':'2026-10-21T00:01:00-03:00','eventos_novos':0}
    path.with_name('audit.log.1').write_text('2026-10-20 22:30:00 '+json.dumps(older)+'\n')
    path.write_text('2026-10-21 00:01:00 '+json.dumps(newer)+'\n')
    items=read_sync_history(path,limit=1,now=datetime(2026,10,21,8,tzinfo=timezone.utc))
    assert len(items)==1 and len(items[0].attempts)==2
    assert items[0].when=='20/10/2026 22:30 (Brasília)'
    assert items[0].new_events==0


def test_agrupamento_preserva_falha_antes_de_espera_e_separa_dias(tmp_path):
    path=tmp_path/'audit.log'
    records=[
        {'result':'ok','quando':'2026-10-20T02:01:00-03:00'},
        {'result':'erro','reason':'consumo_indevido_656','quando':'2026-10-21T02:00:00-03:00'},
        {'result':'ignorado','reason':'cooldown','quando':'2026-10-21T02:02:00-03:00'},
    ]
    path.write_text(''.join('2026-10-21 05:00:00 '+json.dumps(dict(action='sefaz_sync_auto',**p))+'\n' for p in records))
    items=read_sync_history(path,now=datetime(2026,10,21,8,tzinfo=timezone.utc))
    assert len(items)==2 and items[0].result=='Falhou'
    assert '656' in items[0].detail and len(items[0].attempts)==2
    assert items[1].attempts==()
