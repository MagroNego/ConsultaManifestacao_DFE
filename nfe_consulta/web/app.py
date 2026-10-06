"""Aplicação web corporativa."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
import threading
import time
from datetime import date, datetime
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
    executar_consulta,
)
from nfe_consulta.seguranca_banco import criptografado
from nfe_consulta.web.status_view import WebStatus, read_web_status
from nfe_consulta.web.sync_history import read_sync_history
from nfe_consulta.web.admin_history import read_admin_history
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
    clear_admin_cookie,
    set_admin_cookie,
    csrf_token,
    current_user,
    require_admin,
    require_export,
    validate_csrf,
)
from nfe_consulta.web.admin_accounts import AdminAccounts
from nfe_consulta.web.scheduler import loop_sincronizacao_automatica
from nfe_consulta.web.settings import WebSettings, get_settings
from nfe_consulta.web.email_alerts import (
    carregar_destinatarios, salvar_destinatarios, smtp_pronto,
    contar_pendentes, enviar_pendentes, cancelar_pendentes_removidos,
)
from nfe_consulta.web.sync_runtime import sincronizar_configurado
from nfe_consulta.web.uploads import consolidar_txts
from nfe_consulta.web.xml_routes import register_xml_routes
from nfe_consulta.web.xml_store import existing_keys, MAX_UPLOAD, import_history
from nfe_consulta.web.xml_upload_limit import XmlUploadLimit


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _format_date_br(value) -> str:
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


TEMPLATES.env.filters["date_br"] = _format_date_br


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
    return (
        "Banco de manifestações indisponível ou ainda não sincronizado. "
        "Procure o responsável pela aplicação."
    )

def _database_path(settings: WebSettings) -> Path:
    return carregar_caminho_banco(
        settings.database_path,
        path_file=settings.database_path_file,
    )


def _consulta_database_state(settings: WebSettings) -> dict:
    caminho = _database_path(settings)
    if not caminho.is_file():
        return {
            "ready": False,
            "label": "Banco indisponível",
            "notice": "O banco de manifestações ainda não está disponível para consulta.",
        }

    try:
        status = _status_web(settings)
    except Exception:
        return {
            "ready": False,
            "label": "Banco não sincronizado",
            "notice": (
                "O banco de manifestações ainda não está configurado ou sincronizado "
                "para consulta."
            ),
        }

    if status.updated_at is None:
        return {
            "ready": False,
            "label": "Banco não sincronizado",
            "notice": (
                "O banco de manifestações ainda não possui uma sincronização concluída."
            ),
        }

    return {
        "ready": True,
        "label": "Banco disponível",
        "notice": None,
    }


def _database_web(settings: WebSettings) -> dict:
    caminho = _database_path(settings)
    return {
        "path": str(caminho),
        "name": caminho.name,
        "ready": caminho.is_file(),
        "encrypted": criptografado(caminho) if caminho.is_file() else None,
        "configured": bool(
            settings.database_path_file
            and settings.database_path_file.is_file()
        ),
        "password_configured": bool(settings.current_database_password()),
    }


def _status_web(settings: WebSettings) -> WebStatus:
    return read_web_status(
        _database_path(settings),
        CNPJ_PADRAO,
        password=settings.current_database_password(),
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
    app.state.admin_accounts = AdminAccounts(
        settings.admin_accounts_path or settings.database_path.parent / "admin_accounts.db",
        bootstrap_username=settings.admin_username,
        bootstrap_password=settings.admin_password,
    )
    app.state.login_attempts = {}
    app.state.login_lock = threading.Lock()
    app.state.export_lock = threading.Lock()
    app.state.export_active = 0
    app.state.sync_lock = threading.Lock()
    app.state.audit = AuditLog(settings.audit_log)
    app.state.auto_sync_task = None
    app.state.auto_sync_next_at = None

    @app.on_event("startup")
    async def start_auto_sync():
        if not settings.auto_sync_enabled:
            return
        app.state.auto_sync_task = asyncio.create_task(
            loop_sincronizacao_automatica(app)
        )
        app.state.audit.write_system(
            "sefaz_scheduler",
            "iniciado",
            horarios=["08:00", "15:00"],
            dias=list(settings.auto_sync_weekdays),
            data_unica=settings.auto_sync_once_date.isoformat() if settings.auto_sync_once_date else None,
            max_lotes=settings.auto_sync_max_lotes,
        )

    @app.on_event("shutdown")
    async def stop_auto_sync():
        task = app.state.auto_sync_task
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        app.state.audit.write_system(
            "sefaz_scheduler",
            "encerrado",
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        path = request.url.path
        protected = (path.startswith("/atualizar") or
                     (path.startswith("/admin/") and path not in {"/admin/login", "/admin/logout"}) or
                     path == "/xml/importar" or path.startswith("/xml/lote/"))
        if protected and not current_user(request).is_admin:
            if request.method == "GET":
                return RedirectResponse(request.url_for("admin_login_page"), status_code=303,
                    headers={"Cache-Control": "no-store"})
            return JSONResponse({"detail": "Entre para acessar a área Admin."}, status_code=401,
                headers={"Cache-Control": "no-store"})
        if path in {"/excel", "/xml/importar", "/admin/login"} and request.method == "POST":
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Tamanho da requisição inválido."}, status_code=400)
            maximum = MAX_UPLOAD + 2 * 1024 * 1024 if path == "/xml/importar" else settings.max_upload_bytes + 65536 if path == "/excel" else 8192
            if size > maximum:
                return JSONResponse({"detail": "Requisição excede o limite."}, status_code=413)

        export_request = path in {"/excel", "/consulta/exportar", "/xml/exportar"}
        if export_request:
            with app.state.export_lock:
                if app.state.export_active >= 2:
                    return JSONResponse({"detail": "Há exportações em andamento. Tente novamente."}, status_code=429)
                app.state.export_active += 1
        try:
            response = await call_next(request)
        finally:
            if export_request:
                with app.state.export_lock:
                    app.state.export_active -= 1

        if path != "/admin/logout" and admin_session_active(request):
            set_admin_cookie(response, settings, request.cookies[settings.admin_cookie_name],
                secure=request.url.scheme == "https")
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
        if not path.startswith("/static/"):
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
        }

    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login_page(
        request: Request,
        user: Annotated[WebUser, Depends(current_user)],
    ):
        if user.is_admin:
            return RedirectResponse(
                url=request.url_for("atualizar_page" if user.is_admin else "consulta_page"),
                status_code=303,
            )

        return _render(
            request,
            "login.html",
            user,
            admin_configured=app.state.admin_accounts.configured(),
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
        if len(username) > 64 or len(password) > 1024:
            return _render(request, "login.html", user, status_code=400,
                           admin_configured=True, error="Usuário ou senha inválidos.")

        if not app.state.admin_accounts.configured():
            return _render(
                request,
                "login.html",
                user,
                status_code=503,
                admin_configured=False,
                error="Login de administrador ainda não configurado no servidor.",
            )

        address = request.client.host if request.client else "unknown"
        key = ("account", username.strip().casefold())
        ip_key = ("ip", address)
        now = time.monotonic()
        with app.state.login_lock:
            attempts = app.state.login_attempts
            if len(attempts) > 2000:
                for old_key in list(attempts):
                    attempts[old_key] = [t for t in attempts[old_key] if now - t < 300]
                    if not attempts[old_key]:
                        del attempts[old_key]
            recent = [t for t in attempts.get(key, ()) if now - t < 300]
            recent_ip = [t for t in attempts.get(ip_key, ()) if now - t < 300]
            blocked = (len(recent) >= 10 or len(recent_ip) >= 30
                       or (len(attempts) >= 5000 and key not in attempts))
            if not blocked:
                attempts[key] = recent + [now]
                attempts[ip_key] = recent_ip + [now]
        if blocked:
            return _render(request, "login.html", user, status_code=429,
                           admin_configured=True, error="Muitas tentativas. Tente novamente em alguns minutos.")

        logged_username = await run_in_threadpool(app.state.admin_accounts.authenticate, username, password)
        if not logged_username or app.state.admin_accounts.role(logged_username) != "admin":
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
                admin_configured=True,
                error="Usuário ou senha inválidos.",
            )

        with app.state.login_lock:
            app.state.login_attempts.pop(key, None)
        admin_user = WebUser(
            username=logged_username,
            display_name=logged_username,
            is_admin=app.state.admin_accounts.role(logged_username) == "admin",
            role=app.state.admin_accounts.role(logged_username) or "consulta",
        )
        app.state.audit.write(
            request,
            admin_user,
            "admin_login",
            "ok",
        )

        response = RedirectResponse(
            url=request.url_for("atualizar_page" if admin_user.is_admin else "consulta_page"),
            status_code=303,
        )
        set_admin_cookie(response, settings, app.state.admin_accounts.new_session(logged_username),
            secure=request.url.scheme == "https")
        return response

    @app.post("/admin/logout")
    async def admin_logout(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
    ):
        validate_csrf(csrf, user, settings)
        app.state.admin_accounts.revoke_session(user.session_token)
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
        clear_admin_cookie(response, settings, secure=request.url.scheme == "https")
        return response

    @app.get("/admin/historico", response_class=HTMLResponse)
    async def admin_history_page(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
    ):
        try:
            history = await run_in_threadpool(read_admin_history, settings.audit_log)
            error = None
        except OSError:
            history = ()
            error = "Histórico temporariamente indisponível."
        return _render(request, "admin_history.html", user, history=history, error=error)

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
                    database_ready=_consulta_database_state(settings)["ready"],
                    database_status_label=_consulta_database_state(settings)["label"],
                    database_notice=_consulta_database_state(settings)["notice"],
                    filtros=_filtros_iniciais(),
                    tipos_manifestacao=TIPOS_MANIFESTACAO,
                    consultou=True,
                    resultado=None,
                    consulta_error=str(exc),
                )
        else:
            filtros = _filtros_iniciais()

        resultado = None
        xml_keys = set()
        erro_consulta = None
        banco = _database_path(settings)
        database_state = _consulta_database_state(settings)

        if consultou:
            if not database_state["ready"]:
                erro_consulta = database_state["notice"]
            else:
                try:
                    resultado = await run_in_threadpool(
                        consultar_eventos,
                        banco,
                        CNPJ_PADRAO,
                        filtros,
                        password=settings.current_database_password(),
                        pagina=pagina,
                        por_pagina=100,
                    )
                    xml_keys = await run_in_threadpool(existing_keys, banco, CNPJ_PADRAO,
                        [evento.chave for evento in resultado.eventos], password=settings.current_database_password())
                    app.state.audit.write(
                        request,
                        user,
                        "consulta_eventos",
                        "ok",
                        resultados=resultado.total,
                        pagina=resultado.pagina,
                    )
                except Exception as exc:
                    erro_consulta = _database_error_message(exc, settings, user)

        return _render(
            request,
            "consulta.html",
            user,
            database_ready=database_state["ready"],
            database_status_label=database_state["label"],
            database_notice=database_state["notice"],
            filtros=filtros,
            tipos_manifestacao=TIPOS_MANIFESTACAO,
            consultou=consultou,
            resultado=resultado,
            xml_keys=xml_keys,
            consulta_error=erro_consulta,
        )

    @app.get("/consulta/exportar")
    async def exportar_consulta_eventos(
        request: Request,
        user: Annotated[WebUser, Depends(require_export)],
        data_inicial: str = "",
        data_final: str = "",
        numero: str = "",
        serie: str = "",
        chave: str = "",
        codigo: str = "",
    ):
        banco = _database_path(settings)
        database_state = _consulta_database_state(settings)
        if not database_state["ready"]:
            raise HTTPException(
                status_code=503,
                detail=database_state["notice"],
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
                password=settings.current_database_password(),
            )
        except (ValueError, OSError, RuntimeError) as exc:
            app.state.audit.write(
                request,
                user,
                "export_eventos_excel",
                "erro",
                reason=type(exc).__name__,
            )
            raise HTTPException(
                status_code=400,
                detail=_database_error_message(exc, settings, user),
            ) from exc
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
        user: Annotated[WebUser, Depends(require_export)],
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
                database_status_label="Banco indisponível",
                database_notice="O banco de manifestações ainda não está disponível para consulta.",
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
                    senha_banco=settings.current_database_password(),
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
                database_ready=_consulta_database_state(settings)["ready"],
                database_status_label=_consulta_database_state(settings)["label"],
                database_notice=_consulta_database_state(settings)["notice"],
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
                database_ready=_consulta_database_state(settings)["ready"],
                database_status_label=_consulta_database_state(settings)["label"],
                database_notice=_consulta_database_state(settings)["notice"],
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

        try:
            history = await run_in_threadpool(read_sync_history, settings.audit_log)
        except OSError:
            history = ()

        return _render(
            request,
            "status.html",
            user,
            status_web=status_web,
            sync_history=history,
            error=erro,
        )

    @app.get("/atualizar", response_class=HTMLResponse)
    async def atualizar_page(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        ok: str | None = None,
        cert_ok: str | None = None,
        db_ok: str | None = None,
        email_ok: str | None = None,
        email_sent: str | None = None,
        lote: int | None = None,
    ):
        try:
            status_web = await run_in_threadpool(_status_web, settings)
            erro = None
        except Exception as exc:
            status_web = WebStatus(False, None, None, None, None, None, None, None)
            erro = _database_error_message(exc, settings, user)

        try:
            email_recipients = "\n".join(carregar_destinatarios(settings.email_recipients_file))
        except (ValueError, OSError):
            email_recipients = ""
            erro = "Lista de destinatários inválida. Salve novamente os endereços para corrigir."

        batch = None
        if lote is not None:
            try:
                _, batch = await run_in_threadpool(import_history, _database_path(settings),
                    password=settings.current_database_password(), batch_id=lote)
            except Exception:
                erro = "Não foi possível consultar o resultado da importação."

        return _render(
            request,
            "sefaz.html",
            user,
            batch=batch,
            status_web=status_web,
            success=(
                "Sincronização concluída." if ok == "1"
                else "Certificado validado e configurado." if cert_ok == "1"
                else "Banco validado e configurado." if db_ok == "1"
                else "Destinatários dos alertas salvos." if email_ok == "1"
                else f"{email_sent} aviso(s) enviado(s)." if email_sent and email_sent.isdigit()
                else None
            ),
            error=erro,
            certificate_store=settings.certificate_store,
            certificate_fixed=bool(settings.certificate_thumbprint),
            certificate_web=_certificado_web(settings),
            database_web=_database_web(settings),
            cooldown_minutes=settings.sync_cooldown_minutes,
            email_recipients=email_recipients,
            smtp_ready=smtp_pronto(settings),
            email_pending=await run_in_threadpool(contar_pendentes, settings) if status_web.database_ready else None,
        )

    @app.post("/atualizar/alertas-email")
    async def atualizar_alertas_email(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
        recipients: str = Form(""),
    ):
        validate_csrf(csrf, user, settings)
        try:
            emails = salvar_destinatarios(settings.email_recipients_file, recipients)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            await run_in_threadpool(cancelar_pendentes_removidos, settings, emails)
        except (OSError, RuntimeError) as exc:
            app.state.audit.write(request, user, "email_recipients_cleanup", "erro", reason=type(exc).__name__)
        app.state.audit.write(request, user, "email_recipients", "ok", count=len(emails))
        return RedirectResponse(
            url=request.url_for("atualizar_page").include_query_params(email_ok="1"),
            status_code=303,
        )

    @app.post("/atualizar/alertas-email/enviar-pendentes")
    async def atualizar_enviar_pendentes(
        request: Request,
        user: Annotated[WebUser, Depends(require_admin)],
        csrf: str = Form(...),
    ):
        validate_csrf(csrf, user, settings)
        if not smtp_pronto(settings):
            raise HTTPException(status_code=400, detail="Configure o SMTP antes de enviar.")
        enviados = await run_in_threadpool(enviar_pendentes, settings, app.state.audit)
        app.state.audit.write(request, user, "email_retry", "ok", sent=enviados)
        return RedirectResponse(
            url=request.url_for("atualizar_page").include_query_params(email_sent=str(enviados)),
            status_code=303,
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
                settings.current_database_password(),
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
        confirmacao: str = Form(""),
    ):
        validate_csrf(csrf, user, settings)

        if confirmacao != "sincronizar":
            app.state.audit.write(request, user, "sefaz_sync", "ignorado", reason="confirmation_required")
            raise HTTPException(status_code=400, detail="Confirme a sincronização manual antes de continuar.")

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
            app.state.audit.write(request, user, "sefaz_sync", "ignorado", reason="cooldown")
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
            resumo = await run_in_threadpool(
                sincronizar_configurado,
                settings,
                max_lotes=max_lotes,
                audit=app.state.audit,
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

    register_xml_routes(app, settings, _render, _database_path)
    app.add_middleware(XmlUploadLimit)
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
