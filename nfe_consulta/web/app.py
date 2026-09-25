"""Aplicação web corporativa."""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from nfe_consulta import __version__
from nfe_consulta.config import CNPJ_PADRAO, NOME_PLANILHA, UF_PADRAO
from nfe_consulta.servico import (
    ParametrosConsulta,
    ParametrosSincronizacao,
    executar_consulta,
    sincronizar_banco,
)
from nfe_consulta.web.status_view import WebStatus, read_web_status
from nfe_consulta.web.audit import AuditLog
from nfe_consulta.web.auth import (
    WebUser,
    csrf_token,
    current_user,
    require_admin,
    validate_csrf,
)
from nfe_consulta.web.settings import WebSettings, get_settings
from nfe_consulta.web.uploads import consolidar_txts


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _context(
    request: Request,
    user: WebUser | None,
    **extra,
) -> dict:
    settings: WebSettings = request.app.state.settings
    contexto = {
        "request": request,
        "user": user,
        "version": __version__,
        "csrf": csrf_token(user, settings) if user else "",
    }
    contexto.update(extra)
    return contexto


def _render(
    request: Request,
    template: str,
    user: WebUser | None,
    *,
    status_code: int = 200,
    **extra,
):
    extra.setdefault("http_status", status_code)
    return TEMPLATES.TemplateResponse(
        request=request,
        name=template,
        context=_context(request, user, **extra),
        status_code=status_code,
    )



def _database_error_message(
    exc: Exception,
    settings: WebSettings,
    user: WebUser,
) -> str:
    if settings.environment == "development" and user.is_admin:
        return f"{type(exc).__name__}: {exc}"
    return "Não foi possível abrir o banco configurado."

def _status_web(settings: WebSettings) -> WebStatus:
    return read_web_status(
        settings.database_path,
        CNPJ_PADRAO,
        password=settings.database_password,
    )


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Consulta de Manifestação",
        version=__version__,
        root_path=settings.root_path,
        docs_url=None if settings.production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.sync_lock = threading.Lock()
    app.state.audit = AuditLog(settings.audit_log)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        if settings.production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code in {401, 403}:
            user = None
            if exc.status_code == 403:
                try:
                    user = current_user(request)
                except HTTPException:
                    user = None
            return _render(
                request,
                "error.html",
                user,
                status_code=exc.status_code,
                title="Acesso negado",
                message=str(exc.detail),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok",
            "version": __version__,
            "database": settings.database_path.is_file(),
        }

    @app.get("/", response_class=HTMLResponse)
    async def excel_page(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
    ):
        return _render(
            request,
            "excel.html",
            user,
            database_ready=settings.database_path.is_file(),
        )

    @app.post("/excel")
    async def exportar_excel(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
        csrf: str = Form(...),
        files: list[UploadFile] = File(default=[]),
        folder_files: list[UploadFile] = File(default=[]),
    ):
        validate_csrf(csrf, user, settings)

        if not settings.database_path.is_file():
            app.state.audit.write(
                request,
                user,
                "excel",
                "erro",
                reason="database_missing",
            )
            return _render(
                request,
                "excel.html",
                user,
                status_code=503,
                database_ready=False,
                error="Banco de manifestações indisponível no servidor.",
            )

        temporario = Path(tempfile.mkdtemp(prefix="nfe-web-"))
        try:
            chaves = temporario / "CHAVES.txt"
            resumo_upload = await consolidar_txts(
                [*files, *folder_files],
                chaves,
                max_bytes=settings.max_upload_bytes,
                max_chaves=settings.max_keys,
            )
            saida = temporario / NOME_PLANILHA

            resultado = await run_in_threadpool(
                executar_consulta,
                ParametrosConsulta(
                    chaves=chaves,
                    banco=settings.database_path,
                    saida=saida,
                    cnpj=CNPJ_PADRAO,
                    uf=UF_PADRAO,
                    sincronizar_sefaz=False,
                    senha_banco=settings.database_password,
                ),
            )

            app.state.audit.write(
                request,
                user,
                "excel",
                "ok",
                arquivos=resumo_upload.arquivos_txt,
                chaves=resumo_upload.chaves,
                notas=resultado.total,
                com_evento=resultado.com_evento,
                erros=resultado.com_erro,
            )

            return FileResponse(
                path=saida,
                filename=NOME_PLANILHA,
                media_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
                background=BackgroundTask(
                    shutil.rmtree,
                    temporario,
                    ignore_errors=True,
                ),
            )
        except (ValueError, OSError, RuntimeError) as exc:
            shutil.rmtree(temporario, ignore_errors=True)
            app.state.audit.write(
                request,
                user,
                "excel",
                "erro",
                reason=type(exc).__name__,
            )
            return _render(
                request,
                "excel.html",
                user,
                status_code=400,
                database_ready=True,
                error=str(exc),
            )
        except Exception:
            shutil.rmtree(temporario, ignore_errors=True)
            app.state.audit.write(
                request,
                user,
                "excel",
                "erro",
                reason="unexpected",
            )
            return _render(
                request,
                "excel.html",
                user,
                status_code=500,
                database_ready=True,
                error="Não foi possível gerar a planilha.",
            )

    @app.get("/status", response_class=HTMLResponse)
    async def status_page(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
    ):
        try:
            status_web = await run_in_threadpool(_status_web, settings)
            erro = None
        except Exception as exc:
            status_web = WebStatus(False, None, None, None, None, None, None, None)
            erro = _database_error_message(exc, settings, user)

        return _render(
            request,
            "status.html",
            user,
            status_web=status_web,
            error=erro,
        )

    @app.get("/atualizar", response_class=HTMLResponse)
    async def atualizar_page(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        ok: str | None = None,
    ):
        try:
            status_web = await run_in_threadpool(_status_web, settings)
            erro = None
        except Exception as exc:
            status_web = WebStatus(False, None, None, None, None, None, None, None)
            erro = _database_error_message(exc, settings, user)

        return _render(
            request,
            "sefaz.html",
            user,
            status_web=status_web,
            success="Sincronização concluída." if ok == "1" else None,
            error=erro,
            certificate_store=settings.certificate_store,
            certificate_fixed=bool(settings.certificate_thumbprint),
            cooldown_minutes=settings.sync_cooldown_minutes,
        )

    @app.post("/atualizar/sincronizar")
    async def atualizar_sincronizar(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
        max_lotes: int = Form(50),
    ):
        validate_csrf(csrf, user, settings)

        if not 1 <= max_lotes <= 500:
            raise HTTPException(status_code=400, detail="Lotes devem estar entre 1 e 500.")

        status_web = await run_in_threadpool(_status_web, settings)
        if not status_web.database_ready:
            return _render(
                request,
                "sefaz.html",
                user,
                status_code=503,
                status_web=status_web,
                error="Configure um banco existente antes de sincronizar.",
                certificate_store=settings.certificate_store,
                certificate_fixed=bool(settings.certificate_thumbprint),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )

        if not status_web.can_sync:
            return _render(
                request,
                "sefaz.html",
                user,
                status_code=429,
                status_web=status_web,
                error=(
                    "Sincronização bloqueada temporariamente. "
                    f"Nova tentativa disponível em {status_web.available_label}."
                ),
                certificate_store=settings.certificate_store,
                certificate_fixed=bool(settings.certificate_thumbprint),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )

        lock: threading.Lock = app.state.sync_lock
        if not lock.acquire(blocking=False):
            return _render(
                request,
                "sefaz.html",
                user,
                status_code=409,
                status_web=await run_in_threadpool(_status_web, settings),
                error="Já existe uma sincronização em andamento.",
                certificate_store=settings.certificate_store,
                certificate_fixed=bool(settings.certificate_thumbprint),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )

        try:
            resumo = await run_in_threadpool(
                sincronizar_banco,
                ParametrosSincronizacao(
                    banco=settings.database_path,
                    cnpj=CNPJ_PADRAO,
                    uf=UF_PADRAO,
                    max_lotes=max_lotes,
                    senha_banco=settings.database_password,
                    cert_thumbprint=settings.certificate_thumbprint,
                    cert_store=settings.certificate_store,
                    cooldown_minutos=settings.sync_cooldown_minutes,
                ),
            )
            app.state.audit.write(
                request,
                user,
                "sefaz_sync",
                "ok",
                lotes=resumo.lotes,
                eventos_novos=resumo.eventos_novos,
                ult_nsu=resumo.ult_nsu,
                max_nsu=resumo.max_nsu,
                completo=resumo.completo,
                cache=resumo.cache,
                cooldown_minutos=settings.sync_cooldown_minutes,
            )
            return RedirectResponse(
                url=request.url_for("atualizar_page").include_query_params(ok="1"),
                status_code=303,
            )
        except Exception as exc:
            app.state.audit.write(
                request,
                user,
                "sefaz_sync",
                "erro",
                reason=type(exc).__name__,
            )
            try:
                status_web = await run_in_threadpool(_status_web, settings)
            except Exception:
                status_web = WebStatus(False, None, None, None, None, None, None, None)
            return _render(
                request,
                "sefaz.html",
                user,
                status_code=400,
                status_web=status_web,
                error=str(exc),
                certificate_store=settings.certificate_store,
                certificate_fixed=bool(settings.certificate_thumbprint),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )
        finally:
            lock.release()

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "nfe_consulta.web.app:app",
        host=settings.bind_host,
        port=settings.bind_port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        workers=1,
    )


if __name__ == "__main__":
    main()
