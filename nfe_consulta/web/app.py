"""Aplicação web corporativa."""

from __future__ import annotations

import shutil
import tempfile
import threading
from datetime import date
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
from nfe_consulta.banco_config import carregar_caminho_banco, salvar_caminho_banco
from nfe_consulta.config import CNPJ_PADRAO, NOME_PLANILHA, UF_PADRAO
from nfe_consulta.certificado_arquivo import carregar_certificado_arquivo
from nfe_consulta.certificado_config import (
    carregar_config_certificado_arquivo,
    salvar_config_certificado_arquivo,
)
from nfe_consulta.modelos import NfeConsumoIndevidoErro, NfeLimiteConsultaErro
from nfe_consulta.relatorio_eventos import gravar_eventos_xlsx
from nfe_consulta.servico import (
    ParametrosConsulta,
    ParametrosSincronizacao,
    executar_consulta,
    sincronizar_banco,
)
from nfe_consulta.web.status_view import WebStatus, read_web_status
from nfe_consulta.web.audit import AuditLog
from nfe_consulta.web.consulta_local import (
    TIPOS_MANIFESTACAO,
    consultar_eventos,
    consultar_eventos_exportacao,
    normalizar_filtros,
)
from nfe_consulta.web.auth import (
    PUBLIC_USER,
    WebUser,
    admin_session_active,
    authenticate_admin,
    clear_admin_cookie,
    csrf_token,
    current_user,
    require_admin,
    set_admin_cookie,
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

def _database_path(settings: WebSettings) -> Path:
    return carregar_caminho_banco(
        settings.database_path,
        path_file=settings.database_path_file,
    )


def _database_web(settings: WebSettings) -> dict:
    caminho = _database_path(settings)
    return {
        "path": str(caminho),
        "name": caminho.name,
        "ready": caminho.is_file(),
        "configured": bool(
            settings.database_path_file
            and settings.database_path_file.is_file()
        ),
        "password_configured": bool(settings.database_password),
    }


def _status_web(settings: WebSettings) -> WebStatus:
    return read_web_status(
        _database_path(settings),
        CNPJ_PADRAO,
        password=settings.database_password,
    )


def _filtros_iniciais():
    hoje = date.today()
    return normalizar_filtros(
        data_inicial=hoje.replace(day=1).isoformat(),
        data_final=hoje.isoformat(),
    )


def _certificado_web(settings: WebSettings) -> dict:
    config = carregar_config_certificado_arquivo(
        settings.certificate_path_file,
        settings.certificate_password_file,
    )
    if config is not None:
        try:
            certificado = carregar_certificado_arquivo(config.path, config.password)
            return {
                "source": "Arquivo PFX/P12",
                "path": str(config.path),
                "name": config.path.name,
                "subject": certificado.subject,
                "valid_to": certificado.valid_to,
                "ready": True,
                "error": None,
            }
        except Exception as exc:
            return {
                "source": "Arquivo PFX/P12",
                "path": str(config.path),
                "name": config.path.name,
                "subject": None,
                "valid_to": None,
                "ready": False,
                "error": str(exc),
            }

    return {
        "source": settings.certificate_store,
        "path": "",
        "name": "",
        "subject": None,
        "valid_to": None,
        "ready": True,
        "error": None,
    }


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

        if (
            request.url.path != "/admin/logout"
            and admin_session_active(request)
        ):
            set_admin_cookie(response, settings)
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
        if exc.status_code == 401 and request.url.path.startswith("/atualizar"):
            return RedirectResponse(
                url=request.url_for("admin_login_page"),
                status_code=303,
            )
        if exc.status_code in {401, 403}:
            return _render(
                request,
                "error.html",
                current_user(request),
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
            "database": _database_path(settings).is_file(),
        }

    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login_page(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
    ):
        if user.is_admin:
            return RedirectResponse(
                url=request.url_for("atualizar_page"),
                status_code=303,
            )

        return _render(
            request,
            "login.html",
            user,
            admin_username=settings.admin_username,
            admin_configured=bool(settings.admin_password),
        )

    @app.post("/admin/login")
    async def admin_login(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
        csrf: str = Form(...),
        username: str = Form(...),
        password: str = Form(...),
    ):
        validate_csrf(csrf, user, settings)

        if not settings.admin_password:
            return _render(
                request,
                "login.html",
                user,
                status_code=503,
                admin_username=settings.admin_username,
                admin_configured=False,
                error="Login de administrador ainda não configurado no servidor.",
            )

        if not authenticate_admin(username, password, settings):
            app.state.audit.write(
                request,
                PUBLIC_USER,
                "admin_login",
                "erro",
                reason="invalid_credentials",
            )
            return _render(
                request,
                "login.html",
                user,
                status_code=401,
                admin_username=settings.admin_username,
                admin_configured=True,
                error="Usuário ou senha inválidos.",
            )

        admin_user = WebUser(
            username=settings.admin_username,
            display_name="Administrador",
            is_admin=True,
        )
        app.state.audit.write(
            request,
            admin_user,
            "admin_login",
            "ok",
        )

        response = RedirectResponse(
            url=request.url_for("atualizar_page"),
            status_code=303,
        )
        set_admin_cookie(response, settings)
        return response

    @app.post("/admin/logout")
    async def admin_logout(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
    ):
        validate_csrf(csrf, user, settings)
        app.state.audit.write(
            request,
            user,
            "admin_logout",
            "ok",
        )
        response = RedirectResponse(
            url=request.url_for("consulta_page"),
            status_code=303,
        )
        clear_admin_cookie(response, settings)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def home(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
    ):
        return RedirectResponse(
            url=request.url_for("consulta_page"),
            status_code=303,
        )

    @app.get("/consulta", response_class=HTMLResponse)
    async def consulta_page(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
        consultar: str = "",
        data_inicial: str = "",
        data_final: str = "",
        numero: str = "",
        serie: str = "",
        chave: str = "",
        codigo: str = "",
        pagina: int = 1,
    ):
        consultou = consultar == "1" or any(
            valor.strip()
            for valor in (data_inicial, data_final, numero, serie, chave, codigo)
        )

        if consultou:
            try:
                filtros = normalizar_filtros(
                    data_inicial=data_inicial,
                    data_final=data_final,
                    numero=numero,
                    serie=serie,
                    chave=chave,
                    codigo=codigo,
                )
            except ValueError as exc:
                return _render(
                    request,
                    "consulta.html",
                    user,
                    database_ready=_database_path(settings).is_file(),
                    filtros=_filtros_iniciais(),
                    tipos_manifestacao=TIPOS_MANIFESTACAO,
                    consultou=True,
                    resultado=None,
                    consulta_error=str(exc),
                )
        else:
            filtros = _filtros_iniciais()

        resultado = None
        erro_consulta = None
        banco = _database_path(settings)

        if consultou:
            if not banco.is_file():
                erro_consulta = "Banco de manifestações indisponível no servidor."
            else:
                try:
                    resultado = await run_in_threadpool(
                        consultar_eventos,
                        banco,
                        CNPJ_PADRAO,
                        filtros,
                        password=settings.database_password,
                        pagina=pagina,
                        por_pagina=100,
                    )
                    app.state.audit.write(
                        request,
                        user,
                        "consulta_eventos",
                        "ok",
                        resultados=resultado.total,
                        pagina=resultado.pagina,
                    )
                except (ValueError, OSError, RuntimeError) as exc:
                    erro_consulta = str(exc)
                except Exception as exc:
                    erro_consulta = _database_error_message(exc, settings, user)

        return _render(
            request,
            "consulta.html",
            user,
            database_ready=banco.is_file(),
            filtros=filtros,
            tipos_manifestacao=TIPOS_MANIFESTACAO,
            consultou=consultou,
            resultado=resultado,
            consulta_error=erro_consulta,
        )

    @app.get("/consulta/exportar")
    async def exportar_consulta_eventos(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
        data_inicial: str = "",
        data_final: str = "",
        numero: str = "",
        serie: str = "",
        chave: str = "",
        codigo: str = "",
    ):
        banco = _database_path(settings)
        if not banco.is_file():
            raise HTTPException(
                status_code=503,
                detail="Banco de manifestações indisponível no servidor.",
            )

        try:
            filtros = normalizar_filtros(
                data_inicial=data_inicial,
                data_final=data_final,
                numero=numero,
                serie=serie,
                chave=chave,
                codigo=codigo,
            )
            eventos = await run_in_threadpool(
                consultar_eventos_exportacao,
                banco,
                CNPJ_PADRAO,
                filtros,
                password=settings.database_password,
            )
        except (ValueError, OSError, RuntimeError) as exc:
            app.state.audit.write(
                request,
                user,
                "export_eventos_excel",
                "erro",
                reason=type(exc).__name__,
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            app.state.audit.write(
                request,
                user,
                "export_eventos_excel",
                "erro",
                reason="unexpected",
            )
            raise HTTPException(
                status_code=500,
                detail=_database_error_message(exc, settings, user),
            ) from exc

        temporario = Path(tempfile.mkdtemp(prefix="nfe-eventos-web-"))
        inicio = filtros.data_inicial.isoformat() if filtros.data_inicial else "inicio"
        fim = filtros.data_final.isoformat() if filtros.data_final else "atual"
        nome = f"Manifestacoes_{inicio}_a_{fim}.xlsx"
        saida = temporario / nome

        try:
            await run_in_threadpool(
                gravar_eventos_xlsx,
                saida,
                eventos,
                filtros,
            )
        except Exception as exc:
            shutil.rmtree(temporario, ignore_errors=True)
            app.state.audit.write(
                request,
                user,
                "export_eventos_excel",
                "erro",
                reason=type(exc).__name__,
            )
            raise HTTPException(
                status_code=500,
                detail="Não foi possível gerar a planilha da consulta.",
            ) from exc

        app.state.audit.write(
            request,
            user,
            "export_eventos_excel",
            "ok",
            eventos=len(eventos),
        )
        return FileResponse(
            path=saida,
            filename=nome,
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

    @app.post("/excel")
    async def exportar_excel_chaves(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
        csrf: str = Form(...),
        files: UploadFile = File(...),
    ):
        validate_csrf(csrf, user, settings)

        if not _database_path(settings).is_file():
            app.state.audit.write(
                request,
                user,
                "excel_chaves",
                "erro",
                reason="database_missing",
            )
            return _render(
                request,
                "consulta.html",
                user,
                status_code=503,
                database_ready=False,
                filtros=_filtros_iniciais(),
                tipos_manifestacao=TIPOS_MANIFESTACAO,
                consultou=False,
                resultado=None,
                error="Banco de manifestações indisponível no servidor.",
            )

        temporario = Path(tempfile.mkdtemp(prefix="nfe-web-"))
        try:
            chaves = temporario / "CHAVES.txt"
            resumo_upload = await consolidar_txts(
                [files],
                chaves,
                max_bytes=settings.max_upload_bytes,
                max_chaves=settings.max_keys,
            )
            saida = temporario / NOME_PLANILHA

            resultado = await run_in_threadpool(
                executar_consulta,
                ParametrosConsulta(
                    chaves=chaves,
                    banco=_database_path(settings),
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
                "excel_chaves",
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
                "excel_chaves",
                "erro",
                reason=type(exc).__name__,
            )
            return _render(
                request,
                "consulta.html",
                user,
                status_code=400,
                database_ready=True,
                filtros=_filtros_iniciais(),
                tipos_manifestacao=TIPOS_MANIFESTACAO,
                consultou=False,
                resultado=None,
                error=str(exc),
            )
        except Exception:
            shutil.rmtree(temporario, ignore_errors=True)
            app.state.audit.write(
                request,
                user,
                "excel_chaves",
                "erro",
                reason="unexpected",
            )
            return _render(
                request,
                "consulta.html",
                user,
                status_code=500,
                database_ready=True,
                filtros=_filtros_iniciais(),
                tipos_manifestacao=TIPOS_MANIFESTACAO,
                consultou=False,
                resultado=None,
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
        cert_ok: str | None = None,
        db_ok: str | None = None,
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
            success=(
                "Sincronização concluída." if ok == "1"
                else "Certificado validado e configurado." if cert_ok == "1"
                else "Banco validado e configurado." if db_ok == "1"
                else None
            ),
            error=erro,
            certificate_store=settings.certificate_store,
            certificate_fixed=bool(settings.certificate_thumbprint),
            certificate_web=_certificado_web(settings),
            database_web=_database_web(settings),
            cooldown_minutes=settings.sync_cooldown_minutes,
        )

    @app.post("/atualizar/banco")
    async def atualizar_banco_config(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
        database_path: str = Form(...),
    ):
        validate_csrf(csrf, user, settings)

        caminho = database_path.strip()
        if not caminho:
            return RedirectResponse(
                url=request.url_for("atualizar_page"),
                status_code=303,
            )

        try:
            banco = await run_in_threadpool(
                salvar_caminho_banco,
                caminho,
                settings.database_password,
                path_file=settings.database_path_file,
            )
            app.state.audit.write(
                request,
                user,
                "database_config",
                "ok",
                arquivo=banco.name,
            )
            return RedirectResponse(
                url=request.url_for("atualizar_page").include_query_params(db_ok="1"),
                status_code=303,
            )
        except Exception as exc:
            app.state.audit.write(
                request,
                user,
                "database_config",
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
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )

    @app.post("/atualizar/certificado")
    async def atualizar_certificado(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
        certificate_path: str = Form(...),
        certificate_password: str = Form(""),
    ):
        validate_csrf(csrf, user, settings)

        caminho = certificate_path.strip()
        if not caminho:
            return RedirectResponse(
                url=request.url_for("atualizar_page"),
                status_code=303,
            )

        existente = carregar_config_certificado_arquivo(
            settings.certificate_path_file,
            settings.certificate_password_file,
        )
        senha = certificate_password
        if not senha and existente is not None:
            try:
                mesmo_arquivo = (
                    Path(caminho).expanduser().resolve() == existente.path.resolve()
                )
            except OSError:
                mesmo_arquivo = False
            if mesmo_arquivo:
                senha = existente.password

        try:
            certificado = await run_in_threadpool(
                carregar_certificado_arquivo,
                caminho,
                senha,
            )
            if not certificado.cnpj or certificado.cnpj[:8] != CNPJ_PADRAO[:8]:
                raise ValueError(
                    "O certificado não apresenta CNPJ compatível com a empresa."
                )

            config = await run_in_threadpool(
                salvar_config_certificado_arquivo,
                caminho,
                senha,
                path_file=settings.certificate_path_file,
                password_file=settings.certificate_password_file,
            )

            app.state.audit.write(
                request,
                user,
                "certificate_config",
                "ok",
                arquivo=config.path.name,
            )
            return RedirectResponse(
                url=request.url_for("atualizar_page").include_query_params(cert_ok="1"),
                status_code=303,
            )
        except Exception as exc:
            app.state.audit.write(
                request,
                user,
                "certificate_config",
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
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
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
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
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
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
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
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
                cooldown_minutes=settings.sync_cooldown_minutes,
            )

        try:
            cert_arquivo = carregar_config_certificado_arquivo(
                settings.certificate_path_file,
                settings.certificate_password_file,
            )
            resumo = await run_in_threadpool(
                sincronizar_banco,
                ParametrosSincronizacao(
                    banco=_database_path(settings),
                    cnpj=CNPJ_PADRAO,
                    uf=UF_PADRAO,
                    max_lotes=max_lotes,
                    senha_banco=settings.database_password,
                    cert_thumbprint=(
                        None if cert_arquivo is not None else settings.certificate_thumbprint
                    ),
                    cert_store=settings.certificate_store,
                    cert_arquivo=cert_arquivo.path if cert_arquivo is not None else None,
                    cert_senha_arquivo=(
                        cert_arquivo.password if cert_arquivo is not None else None
                    ),
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
            http_status = (
                429
                if isinstance(exc, (NfeConsumoIndevidoErro, NfeLimiteConsultaErro))
                else 400
            )
            return _render(
                request,
                "sefaz.html",
                user,
                status_code=http_status,
                status_web=status_web,
                error=str(exc),
                certificate_store=settings.certificate_store,
                certificate_fixed=bool(settings.certificate_thumbprint),
                certificate_web=_certificado_web(settings),
                database_web=_database_web(settings),
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
