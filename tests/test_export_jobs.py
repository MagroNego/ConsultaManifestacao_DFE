import asyncio
from pathlib import Path
import runpy

import httpx
from fastapi import Request
from fastapi.routing import APIRoute
from fastapi.responses import Response

from nfe_consulta.web.app import create_app
from nfe_consulta.web.downloads import archive_file
from nfe_consulta.web.export_queue import ExportQueue
from nfe_consulta.web import xml_store
from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.web.auth import PUBLIC_USER, csrf_token

helpers = runpy.run_path(str(Path(__file__).with_name('test_xml_integrado.py')))
web = helpers['helpers']


def test_background_jobs_survive_navigation_show_queue_and_publish_archive(tmp_path):
    async def scenario():
        app = create_app(web['settings_web'](tmp_path))
        app.state.export_queue = ExportQueue(concurrency=1, max_waiting=1)
        release = asyncio.Event()
        entered = asyncio.Event()
        async def generate(request: Request):
            entered.set()
            await release.wait()
            await archive_file(request, b'report', filename='Notas.csv', media_type='text/csv',
                               documents=4, period='01/10/2026')
            return Response(b'report', media_type='text/csv')
        for route in app.routes:
            if getattr(route, 'path', '') == '/xml/exportar':
                route.app = APIRoute('/xml/exportar', generate, methods=['GET']).app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            first = await client.get('/xml/exportar?data_inicial=01/10/2026', headers={'X-NFE-Background': '1'})
            assert first.status_code == 202
            first_id = first.json()['job_id']
            await asyncio.wait_for(entered.wait(), 2)
            second = await client.get('/xml/exportar', headers={'X-NFE-Background': '1'})
            second_id = second.json()['job_id']
            overflow = await client.get('/xml/exportar', headers={'X-NFE-Background': '1'})
            assert overflow.status_code == 429
            await client.get('/xml')  # Mudar de página não cancela a tarefa.
            state = (await client.get('/downloads/estado', params={'ids': first_id + ',' + second_id})).json()
            assert {item['status'] for item in state['jobs']} == {'generating', 'queued'}
            assert 'Na fila' in state['html'] and 'Gerando arquivo' in state['html']
            assert 'A partir de 01/10/2026' in state['html']
            release.set()
            await asyncio.wait_for(asyncio.gather(*list(app.state.export_jobs.tasks)), 3)
            state = (await client.get('/downloads/estado', params={'ids': first_id + ',' + second_id})).json()
            assert all(item['status'] == 'complete' for item in state['jobs'])
            assert 'Gerando arquivo' not in state['html']
            assert 'Pronto' in state['html']
            assert len(app.state.downloads.list()) == 2
            for job in state['jobs']:
                assert (await client.get('/downloads/' + job['archive_id'])).content == b'report'
        await app.state.export_jobs.close()
    asyncio.run(scenario())


def test_real_csv_background_export_and_error(tmp_path):
    async def scenario():
        cfg = web['settings_web'](tmp_path)
        web['criar_banco'](cfg.database_path)
        source = tmp_path / 'nota.xml'
        source.write_bytes(helpers['xml']())
        xml_store.import_batch(cfg.database_path, CNPJ_PADRAO, [(source, 'nota.xml')])
        app = create_app(cfg)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            success = await client.get('/xml/exportar?formato=csv&tipo=itens', headers={'X-NFE-Background': '1'})
            failure = await client.get('/xml/exportar?formato=invalid', headers={'X-NFE-Background': '1'})
            await asyncio.wait_for(asyncio.gather(*list(app.state.export_jobs.tasks)), 5)
            state = (await client.get('/downloads/estado', params={'ids': success.json()['job_id'] + ',' + failure.json()['job_id']})).json()
            assert {job['status'] for job in state['jobs']} == {'complete', 'error'}
            assert 'Erro na geração' in state['html']
            archive = app.state.downloads.list()[0]
            assert archive['filename'] == 'Leitor_XML.csv' and archive['documents'] == 1
            assert (await client.get('/downloads/' + archive['id'])).status_code == 200
        await app.state.export_jobs.close()
    asyncio.run(scenario())


def test_background_post_preserves_body_and_shutdown_marks_error(tmp_path):
    async def scenario():
        app = create_app(web['settings_web'](tmp_path))
        entered = asyncio.Event()
        async def generate(request: Request):
            assert await request.body() == b'original multipart body'
            entered.set()
            await asyncio.Event().wait()
        for route in app.routes:
            if getattr(route, 'path', '') == '/excel':
                route.app = APIRoute('/excel', generate, methods=['POST']).app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/excel', content=b'original multipart body', headers={'X-NFE-Background': '1'})
            assert response.status_code == 202
            await asyncio.wait_for(entered.wait(), 2)
            await app.state.export_jobs.close()
            assert app.state.export_jobs.records[response.json()['job_id']]['status'] == 'error'
            assert app.state.export_queue.active == app.state.export_queue.waiting == 0
    asyncio.run(scenario())


def test_real_txt_background_export_still_validates_csrf(tmp_path):
    async def scenario():
        cfg = web['settings_web'](tmp_path)
        web['criar_banco'](cfg.database_path)
        app = create_app(cfg)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            ids = []
            for token in (csrf_token(PUBLIC_USER, cfg), 'invalid'):
                response = await client.post('/excel', data={'csrf': token},
                    files={'files': ('chaves.txt', helpers['CHAVE'].encode(), 'text/plain')},
                    headers={'X-NFE-Background': '1'})
                assert response.status_code == 202
                ids.append(response.json()['job_id'])
            await asyncio.wait_for(asyncio.gather(*list(app.state.export_jobs.tasks)), 5)
            states = app.state.export_jobs.records
            assert states[ids[0]]['status'] == 'complete'
            assert states[ids[1]]['status'] == 'error'
            assert len(app.state.downloads.list()) == 1
        await app.state.export_jobs.close()
    asyncio.run(scenario())
