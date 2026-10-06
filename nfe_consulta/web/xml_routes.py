"""Rotas do leitor XML integradas às sessões e ao banco da aplicação."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as MultipartUploadFile

from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.web.auth import WebUser, current_user, require_admin, require_export, require_user, validate_csrf
from nfe_consulta.web.consulta_local import normalizar_filtros
from nfe_consulta.web import xml_store as store


def register_xml_routes(app, settings, render, database_path):
    def filters(inicio, fim):
        return normalizar_filtros(data_inicial=inicio, data_final=fim)

    @app.get("/xml")
    async def xml_page(request: Request, user: Annotated[WebUser, Depends(require_user)],
                       tipo: str = "notas", q: str = "", data_inicial: str = "",
                       data_final: str = "", pagina: int = 1, lote: int | None = None):
        error = None
        result = dict(rows=[], columns=[], total=0, page=1, pages=0, notas=0)
        history, batch = [], None
        selected = None
        try:
            selected = filters(data_inicial, data_final)
            result = await run_in_threadpool(store.query_report, database_path(settings), CNPJ_PADRAO,
                password=settings.current_database_password(), kind=tipo, query=q,
                inicio=selected.data_inicial, fim=selected.data_final, page=pagina)
            if user.is_admin:
                history, batch = await run_in_threadpool(store.import_history, database_path(settings),
                    password=settings.current_database_password(), batch_id=lote)
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = "Não foi possível abrir o arquivo de XMLs. Confira a configuração do banco."
        return render(request, "xml.html", user, result=result, tipo=tipo, q=q,
            inicio=selected.data_inicial_br if selected else data_inicial,
            fim=selected.data_final_br if selected else data_final,
            history=history, batch=batch, error=error)

    @app.post("/xml/importar")
    async def xml_import(request: Request, user: Annotated[WebUser, Depends(require_admin)]):
        # Os parâmetros File/Form do FastAPI usam max_files=1000 antes da rota.
        # Faça o parse com o mesmo teto anunciado para o lote, apenas nesta rota.
        async with request.form(max_files=store.MAX_FILES, max_fields=1,
                                max_part_size=4096) as form:
            csrf = form.get("csrf")
            if not isinstance(csrf, str):
                raise HTTPException(403, "Token de segurança inválido.")
            validate_csrf(csrf, user, settings)
            files = form.getlist("files")
            if not files or any(not isinstance(upload, MultipartUploadFile) for upload in files):
                raise HTTPException(400, "Selecione arquivos XML ou ZIP para importar.")
            return await process_xml_import(request, user, files)

    async def process_xml_import(request, user, files):
        total = 0
        try:
            if len(files) > store.MAX_FILES:
                raise HTTPException(413, "Lote excede 5.000 arquivos.")
            with tempfile.TemporaryDirectory(prefix="nfe_xml_") as temp:
                paths = []
                for index, upload in enumerate(files):
                    filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
                    if Path(filename).suffix.lower() not in (".xml", ".zip"):
                        raise HTTPException(400, "Selecione somente XMLs ou arquivos ZIP.")
                    path = Path(temp) / f"{index}.upload"
                    with path.open("wb") as out:
                        while True:
                            chunk = await upload.read(64 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > store.MAX_UPLOAD:
                                raise HTTPException(413, "Envio excede 100 MiB. Divida o lote.")
                            out.write(chunk)
                    paths.append((path, filename))
                lock = app.state.sync_lock
                if not lock.acquire(blocking=False):
                    raise HTTPException(409, "Há uma sincronização ou importação em andamento. Aguarde.")
                try:
                    summary = await run_in_threadpool(store.import_batch, database_path(settings), CNPJ_PADRAO,
                        paths, password=settings.current_database_password(), user=user.username)
                finally:
                    lock.release()
        except ValueError as exc:
            app.state.audit.write(request, user, "xml_import", "erro", reason=type(exc).__name__)
            raise HTTPException(400, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            app.state.audit.write(request, user, "xml_import", "erro", reason=type(exc).__name__)
            raise HTTPException(400, "Não foi possível importar o lote. Confira o banco e os arquivos.") from exc
        finally:
            for upload in files:
                await upload.close()
        app.state.audit.write(request, user, "xml_import", "ok", lote=summary["id"],
            importadas=summary["importadas"], duplicadas=summary["duplicadas"], erros=summary["erros"])
        return RedirectResponse(request.url_for("xml_page").include_query_params(lote=summary["id"]), status_code=303)

    @app.get("/xml/arquivo/{chave}")
    async def xml_download(request: Request, chave: str, user: Annotated[WebUser, Depends(require_export)]):
        if len(chave) != 44 or not chave.isdigit():
            raise HTTPException(400, "Chave de acesso inválida.")
        try:
            data = await run_in_threadpool(store.download_xml, database_path(settings), CNPJ_PADRAO,
                chave, password=settings.current_database_password())
        except Exception as exc:
            raise HTTPException(503, "Arquivo de XMLs indisponível.") from exc
        if data is None:
            raise HTTPException(404, "XML ainda não importado. Envie o lote mensal no leitor.")
        app.state.audit.write(request, user, "xml_download", "ok")
        return Response(data, media_type="application/xml", headers={
            "Content-Disposition": f'attachment; filename="{chave}.xml"', "Cache-Control": "no-store"})

    @app.get("/xml/exportar")
    async def xml_export(request: Request, user: Annotated[WebUser, Depends(require_export)],
                         formato: str = "xlsx", tipo: str = "itens", q: str = "",
                         data_inicial: str = "", data_final: str = "", lote: int | None = None):
        if formato not in ("xlsx", "csv") or tipo not in ("notas", "itens", "retencoes"):
            raise HTTPException(400, "Formato ou relatório inválido.")
        def generate():
            selected = filters(data_inicial, data_final)
            kwargs = dict(password=settings.current_database_password(), query=q,
                          inicio=selected.data_inicial, fim=selected.data_final, export=True)
            if formato == "csv":
                return store.export_csv(store.query_report(database_path(settings), CNPJ_PADRAO, kind=tipo, **kwargs))
            reports = [(title, store.query_report(database_path(settings), CNPJ_PADRAO, kind=kind, **kwargs))
                for title, kind in (("Notas", "notas"), ("Itens", "itens"), ("Retencoes", "retencoes"))]
            return store.export_excel(reports)
        try:
            data = await run_in_threadpool(generate)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Não foi possível gerar o relatório. Confira o banco.") from exc
        app.state.audit.write(request, user, "xml_export", "ok", formato=formato)
        media = "text/csv" if formato == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="Leitor_XML.{formato}"'})

    @app.get("/xml/lote/{lote}/registro")
    async def xml_batch_log(request: Request, lote: int, user: Annotated[WebUser, Depends(require_admin)]):
        try:
            _, batch = await run_in_threadpool(store.import_history, database_path(settings),
                password=settings.current_database_password(), batch_id=lote)
        except Exception as exc:
            raise HTTPException(503, "Registro de importação indisponível.") from exc
        if batch is None:
            raise HTTPException(404, "Lote não encontrado.")
        data = store.export_csv(dict(columns=["arquivo", "status", "mensagem"], rows=batch["registros"]))
        return Response(data, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="Importacao_XML_{lote}.csv"'})
