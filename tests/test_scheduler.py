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


def test_teste_unico_em_30_09_as_09_brasilia():
    alvo = scheduler.horario_unico(date(2026, 9, 30), 9, 0)
    assert alvo.isoformat() == "2026-09-30T09:00:00-03:00"
    assert alvo.astimezone(timezone.utc).hour == 12


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


def test_teste_unico_registra_tentativa_antes_e_nao_repete(monkeypatch):
    dia = date(2026, 9, 30)
    registrado = []
    chamadas = []
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(), audit=None))

    monkeypatch.setattr(scheduler, "ultima_execucao_agendada",
                        lambda _: registrado[-1] if registrado else None)
    monkeypatch.setattr(scheduler, "registrar_execucao_agendada",
                        lambda _, data: registrado.append(data))

    async def executar(_, *, dia_agendado):
        assert registrado == [dia]
        chamadas.append(dia_agendado)

    monkeypatch.setattr(scheduler, "executar_sincronizacao_automatica", executar)
    asyncio.run(scheduler.executar_sincronizacao_unica(app, dia))
    asyncio.run(scheduler.executar_sincronizacao_unica(app, dia))
    assert registrado == [dia]
    assert chamadas == [dia]


def test_loop_unico_espera_ate_09_e_termina(monkeypatch):
    alvo = scheduler.horario_unico(date(2026, 9, 30), 9, 0)
    instantes = iter((alvo.replace(hour=8, minute=30), alvo))
    monkeypatch.setattr(scheduler, "agora_brasilia", lambda: next(instantes))
    esperado = []

    async def dormir(segundos):
        esperado.append(segundos)

    async def executar(_, dia):
        esperado.append(dia)

    monkeypatch.setattr(scheduler.asyncio, "sleep", dormir)
    monkeypatch.setattr(scheduler, "executar_sincronizacao_unica", executar)
    app = SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(auto_sync_once_date=alvo.date(),
                                 auto_sync_hour=9, auto_sync_minute=0),
        auto_sync_next_at=None,
    ))
    asyncio.run(scheduler.loop_sincronizacao_automatica(app))
    assert esperado == [1800.0, alvo.date()]
    assert app.state.auto_sync_next_at is None



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



def test_janelas_oito_horas_usam_brasilia_em_fins_de_semana():
    # 19:00 UTC = 16:00 Brasília; sábado também tem janela.
    agora = datetime(2026, 10, 3, 19, tzinfo=timezone.utc)
    atual, proxima = scheduler.janelas_intervalo(agora)
    assert atual.isoformat() == "2026-10-03T16:00:00-03:00"
    assert proxima.isoformat() == "2026-10-04T00:00:00-03:00"
    atual, proxima = scheduler.janelas_intervalo(agora.replace(hour=18, minute=59))
    assert atual.hour == 8
    assert proxima.hour == 16


def test_persistencia_distingue_tres_janelas_e_sobrevive_a_reinicio(tmp_path):
    from nfe_consulta.banco import BancoManifestacoes
    caminho = tmp_path / "banco.db"
    BancoManifestacoes(str(caminho)).fechar()
    cfg = SimpleNamespace(database_path=caminho, database_path_file=None,
                          current_database_password=lambda: None)
    assert scheduler.ultima_janela_concluida(cfg) is None
    for hora in (0, 8, 16):
        janela = scheduler.horario_unico(date(2026, 9, 30), hora, 0)
        scheduler.registrar_janela_concluida(cfg, janela)
        # A leitura reabre o arquivo; não depende de estado em memória.
        assert scheduler.ultima_janela_concluida(cfg) == janela


def test_loop_nao_repete_janela_concluida_apos_reinicio(monkeypatch):
    atual = scheduler.horario_unico(date(2026, 9, 30), 8, 0)
    monkeypatch.setattr(scheduler, "agora_brasilia", lambda: atual.replace(hour=9))
    monkeypatch.setattr(scheduler, "ultima_janela_concluida", lambda _: atual)
    chamadas = []
    async def executar(*args, **kwargs):
        chamadas.append(kwargs)
    async def encerrar(_):
        raise asyncio.CancelledError
    monkeypatch.setattr(scheduler, "executar_sincronizacao_automatica", executar)
    monkeypatch.setattr(scheduler.asyncio, "sleep", encerrar)
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
        auto_sync_once_date=None, auto_sync_interval_hours=8,
        auto_sync_hour=8, auto_sync_minute=0, auto_sync_weekdays=tuple(range(7)),
    )))
    try:
        asyncio.run(scheduler.loop_sincronizacao_automatica(app))
    except asyncio.CancelledError:
        pass
    assert chamadas == []
    assert app.state.auto_sync_next_at.hour == 16


def test_loop_recupera_so_a_janela_mais_recente(monkeypatch):
    atual = scheduler.horario_unico(date(2026, 10, 4), 16, 0)
    monkeypatch.setattr(scheduler, "agora_brasilia", lambda: atual.replace(hour=17))
    monkeypatch.setattr(scheduler, "ultima_janela_concluida", lambda _: atual.replace(day=1))
    chamadas = []
    async def executar(*args, **kwargs):
        chamadas.append(kwargs["janela_agendada"])
    async def encerrar(_):
        raise asyncio.CancelledError
    monkeypatch.setattr(scheduler, "executar_sincronizacao_automatica", executar)
    monkeypatch.setattr(scheduler.asyncio, "sleep", encerrar)
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
        auto_sync_once_date=None, auto_sync_interval_hours=8,
        auto_sync_hour=8, auto_sync_minute=0, auto_sync_weekdays=tuple(range(7)),
    )))
    try:
        asyncio.run(scheduler.loop_sincronizacao_automatica(app))
    except asyncio.CancelledError:
        pass
    assert chamadas == [atual]


def test_distribuicao_parcial_nao_conclui_janela(monkeypatch):
    registros = []
    class Audit:
        def write_system(self, *args, **kwargs):
            pass
    cfg = SimpleNamespace(auto_sync_max_lotes=50, sync_cooldown_minutes=120)
    app = SimpleNamespace(state=SimpleNamespace(settings=cfg, sync_lock=threading.Lock(), audit=Audit()))
    monkeypatch.setattr(scheduler, "registrar_janela_concluida", lambda *args: registros.append(args))
    monkeypatch.setattr(scheduler, "sincronizar_configurado", lambda *args, **kwargs: SimpleNamespace(
        lotes=50, eventos_novos=1, ult_nsu="1", max_nsu="2", completo=False, cache=False))
    asyncio.run(scheduler.executar_sincronizacao_automatica(
        app, janela_agendada=scheduler.horario_unico(date(2026, 9, 30), 8, 0)))
    assert registros == []
