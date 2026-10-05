"""Limite do corpo antes do parser multipart, inclusive sem Content-Length."""
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from nfe_consulta.web.xml_store import MAX_UPLOAD


class _UploadTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Envio excede 100 MiB. Divida o lote.")


class XmlUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/xml/importar" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        limit = MAX_UPLOAD + 2 * 1024 * 1024
        size = 0
        started = False
        exceeded = False
        replaced = False
        async def limited_receive():
            nonlocal size, exceeded
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    exceeded = True
                    raise _UploadTooLarge()
            return message
        async def tracked_send(message):
            nonlocal started, replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    await JSONResponse({"detail": "Envio excede 100 MiB. Divida o lote."}, status_code=413)(scope, receive, send)
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)
        try:
            await self.app(scope, limited_receive, tracked_send)
        except _UploadTooLarge:
            if started:
                raise
            await JSONResponse({"detail": "Envio excede 100 MiB. Divida o lote."}, status_code=413)(scope, receive, send)
