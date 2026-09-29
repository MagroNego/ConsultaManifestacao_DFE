import asyncio
import threading
from datetime import date, datetime, timezone
from types import SimpleNamespace

from nfe_consulta.web import scheduler


def test_proxima_execucao_em_dia_util():
    segunda = datetime(2026, 9, 28, 7, 30, tzinfo=timezone.utc)

    proxima = scheduler.proxima_execucao(
        segunda,
        hora=8,
        minuto=0,
        dias_semana=(0, 1, 2, 3, 4),
    )

    assert proxima == datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)


def test_proxima_execucao_pula_fim_de_semana():
    sexta = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)

    proxima = scheduler.proxima_execucao(
        sexta,
        hora=8,
        minuto=0,
        dias_semana=(0, 1, 2, 3, 4),
    )

    assert proxima == datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)


def test_sincronizacao_automatica_usa_mesmo_lock_da_web(monkeypatch):
    eventos = []

    class Audit:
        def write_system(self, action, result, **details):
            eventos.append((action, result, details))

    settings = SimpleNamespace(
        auto_sync_max_lotes=50,
        sync_cooldown_minutes=120,
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=settings,
            sync_lock=threading.Lock(),
            audit=Audit(),
        )
    )

    monkeypatch.setattr(
        scheduler,
        "registrar_execucao_agendada",
        lambda _settings, _dia: None,
    )
    monkeypatch.setattr(
        scheduler,
        "sincronizar_configurado",
        lambda _settings, *, max_lotes, audit=None: SimpleNamespace(
            lotes=1,
            eventos_novos=2,
            ult_nsu="000000000000010",
            max_nsu="000000000000010",
            completo=True,
            cache=False,
        ),
    )

    asyncio.run(scheduler.executar_sincronizacao_automatica(app))

    assert eventos[0][0] == "sefaz_sync_auto"
    assert eventos[0][1] == "ok"
    assert eventos[0][2]["eventos_novos"] == 2
    assert app.state.sync_lock.acquire(blocking=False)
    app.state.sync_lock.release()


def test_sincronizacao_automatica_nao_concorre_com_manual(monkeypatch):
    eventos = []

    class Audit:
        def write_system(self, action, result, **details):
            eventos.append((action, result, details))

    monkeypatch.setattr(
        scheduler,
        "registrar_execucao_agendada",
        lambda _settings, _dia: None,
    )

    lock = threading.Lock()
    lock.acquire()
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(
                auto_sync_max_lotes=50,
                sync_cooldown_minutes=120,
            ),
            sync_lock=lock,
            audit=Audit(),
        )
    )

    try:
        asyncio.run(scheduler.executar_sincronizacao_automatica(app))
    finally:
        lock.release()

    assert eventos == [
        (
            "sefaz_sync_auto",
            "ignorado",
            {"reason": "sync_in_progress"},
        )
    ]


def test_falha_automatica_nao_marca_dia_como_concluido(monkeypatch):
    passos = []
    class Audit:
        def write_system(self, action, result, **details):
            passos.append(result)

    app = SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(auto_sync_max_lotes=50, sync_cooldown_minutes=120),
        sync_lock=threading.Lock(), audit=Audit(),
    ))
    monkeypatch.setattr(scheduler, "registrar_execucao_agendada",
                        lambda *args: passos.append("marcado"))
    def falhar(*args, **kwargs):
        raise OSError("indisponível")
    monkeypatch.setattr(scheduler, "sincronizar_configurado", falhar)
    asyncio.run(scheduler.executar_sincronizacao_automatica(app))
    assert passos == ["erro"]



def test_recupera_execucao_quando_servidor_sobe_depois_do_horario():
    agora = datetime(2026, 9, 28, 8, 15, tzinfo=timezone.utc)

    assert scheduler.deve_recuperar_execucao(
        agora,
        None,
        hora=8,
        minuto=0,
        dias_semana=(0, 1, 2, 3, 4),
    )


def test_nao_repete_recuperacao_no_mesmo_dia():
    agora = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)

    assert not scheduler.deve_recuperar_execucao(
        agora,
        date(2026, 9, 28),
        hora=8,
        minuto=0,
        dias_semana=(0, 1, 2, 3, 4),
    )


def test_nao_recupera_antes_do_horario():
    agora = datetime(2026, 9, 28, 7, 59, tzinfo=timezone.utc)

    assert not scheduler.deve_recuperar_execucao(
        agora,
        date(2026, 9, 26),
        hora=8,
        minuto=0,
        dias_semana=(0, 1, 2, 3, 4),
    )
