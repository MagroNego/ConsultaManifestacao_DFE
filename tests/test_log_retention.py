import json
from datetime import datetime, timedelta, timezone

from nfe_consulta.web.audit import AuditLog
from nfe_consulta.web.log_retention import prune_sync_logs
from nfe_consulta.web.sync_history import read_sync_history

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def record(instant, action='sefaz_sync_auto', **extra):
    return f'{instant:%Y-%m-%d %H:%M:%S} ' + json.dumps(dict(
        action=action, result='ok', logged_at_utc=instant.isoformat(), **extra)) + '\n'


def test_retencao_limite_30_dias_e_preserva_admin_e_linhas_invalidas(tmp_path):
    path = tmp_path / 'web_audit.log'
    old = NOW - timedelta(days=30, seconds=1)
    boundary = NOW - timedelta(days=30)
    admin = record(old, 'admin_accounts')
    invalid = 'linha incompleta\n'
    path.write_text(record(old) + record(boundary) + admin + invalid)
    rotated = path.with_name(path.name + '.5')
    rotated.write_text(record(old, 'sefaz_sync') + record(NOW))
    untouched = tmp_path / 'outro.log'
    untouched.write_text(record(old))
    assert prune_sync_logs(path, now=NOW) == 2
    assert path.read_text() == record(boundary) + admin + invalid
    assert rotated.read_text() == record(NOW)
    assert untouched.read_text() == record(old)
    assert prune_sync_logs(path, now=NOW) == 0
    assert list(tmp_path.glob('*.tmp')) == []


def test_historico_filtra_30_dias_inclusive_em_rotacoes(tmp_path):
    path = tmp_path / 'web_audit.log'
    path.write_text(record(NOW - timedelta(days=31)))
    path.with_name(path.name + '.1').write_text(record(NOW, lotes=2))
    items = read_sync_history(path, now=NOW)
    assert len(items) == 1
    assert items[0].lots == 2


def test_falha_substituicao_preserva_original(tmp_path, monkeypatch):
    path = tmp_path / 'web_audit.log'
    original = record(NOW - timedelta(days=31))
    path.write_text(original)
    def fail(*args):
        raise OSError('falha simulada')
    monkeypatch.setattr('nfe_consulta.web.log_retention.os.replace', fail)
    import pytest
    with pytest.raises(OSError):
        prune_sync_logs(path, now=NOW)
    assert path.read_text() == original
    assert list(tmp_path.glob('*.tmp')) == []


def test_limpeza_inicial_e_diaria_sem_reiniciar_app(tmp_path, monkeypatch):
    from nfe_consulta.web import audit
    class Clock(datetime):
        instant = NOW
        @classmethod
        def now(cls, tz=None):
            return cls.instant if tz else cls.instant.replace(tzinfo=None)
    monkeypatch.setattr(audit, 'datetime', Clock)
    # prune_sync_logs recebe o instante do handler, inclusive para testes.
    path = tmp_path / 'web_audit.log'
    path.write_text(record(NOW - timedelta(days=31)))
    logger = AuditLog(path)
    logger.write_system('sefaz_sync_auto', 'ok')
    assert len(path.read_text().splitlines()) == 1
    Clock.instant = NOW + timedelta(days=31)
    logger.write_system('sefaz_sync_auto', 'ok')
    assert len(path.read_text().splitlines()) == 1
    text = path.read_text()
    payload = json.loads(text[text.index('{'):])
    assert payload['logged_at_utc'] == Clock.instant.isoformat()
