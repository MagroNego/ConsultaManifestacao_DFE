import asyncio
from pathlib import Path
import runpy

import httpx
import pytest
from fastapi import Request
from fastapi.responses import Response

from nfe_consulta.web.app import create_app
from nfe_consulta.web.export_queue import ExportQueue, ExportQueueBusy

web = runpy.run_path(str(Path(__file__).with_name('test_web.py')))


async def settle():
    for _ in range(10):
        await asyncio.sleep(0)


def test_parallel_exports_wait_and_fifo_release():
    async def scenario():
        queue = ExportQueue(concurrency=2, max_waiting=3)
        releases = [asyncio.Event() for _ in range(4)]
        started = []
        async def worker(index):
            async with queue.slot():
                started.append(index)
                await releases[index].wait()
        tasks = [asyncio.create_task(worker(i)) for i in range(4)]
        await settle()
        assert started == [0, 1]
        assert queue.active == 2 and queue.waiting == 2
        releases[0].set()
        await settle()
        assert started == [0, 1, 2]
        releases[1].set()
        await settle()
        assert started == [0, 1, 2, 3]
        releases[2].set()
        releases[3].set()
        await asyncio.gather(*tasks)
        assert queue.active == queue.waiting == 0
    asyncio.run(scenario())


def test_capacity_timeout_cancellation_and_failures_release_slots():
    async def scenario():
        queue = ExportQueue(concurrency=1, max_waiting=1, timeout=0.05)
        entered = asyncio.Event()
        release = asyncio.Event()
        async def worker():
            async with queue.slot():
                entered.set()
                await release.wait()
        active = asyncio.create_task(worker())
        await entered.wait()
        waiter = asyncio.create_task(worker())
        await settle()
        with pytest.raises(ExportQueueBusy) as error:
            async with queue.slot():
                pass
        assert error.value.status_code == 429
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert queue.active == 1 and queue.waiting == 0
        with pytest.raises(ExportQueueBusy) as error:
            async with queue.slot():
                pass
        assert error.value.status_code == 503
        assert queue.waiting == 0
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        with pytest.raises(RuntimeError):
            async with queue.slot():
                raise RuntimeError('generation failed')
        async with queue.slot():
            assert queue.active == 1
        assert queue.active == queue.waiting == 0
    asyncio.run(scenario())


def test_http_third_export_waits_and_archived_download_bypasses_queue(tmp_path):
    async def scenario():
        cfg = web['settings_web'](tmp_path)
        app = create_app(cfg)
        app.state.export_queue = ExportQueue(timeout=2)
        entered = []
        release = asyncio.Event()
        # Same real protected path, substitute only generation to control ordering.
        async def generation(request: Request):
            entered.append(request)
            await release.wait()
            return Response(b'report', media_type='text/csv')
        for route in app.routes:
            if getattr(route, 'path', '') == '/xml/exportar':
                from fastapi.routing import APIRoute
                replacement = APIRoute('/xml/exportar', generation, methods=['GET'])
                route.app = replacement.app
                break
        item = app.state.downloads.save(b'archived', filename='ready.csv', media_type='text/csv', documents=1, period='Não informado')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            tasks = [asyncio.create_task(client.get('/xml/exportar')) for _ in range(3)]
            # Await signals via loop until two requests entered generation.
            for _ in range(200):
                if len(entered) == 2 and app.state.export_queue.waiting == 1:
                    break
                await asyncio.sleep(0)
            assert len(entered) == 2 and app.state.export_queue.waiting == 1
            assert all(not task.done() for task in tasks)
            ready = await client.get('/downloads/' + item['id'])
            assert ready.status_code == 200 and ready.content == b'archived'
            assert len(entered) == 2
            release.set()
            results = await asyncio.gather(*tasks)
            assert [r.status_code for r in results] == [200, 200, 200]
            assert all(r.content == b'report' for r in results)
        assert len(entered) == 3
        assert app.state.export_queue.active == app.state.export_queue.waiting == 0
    asyncio.run(scenario())
