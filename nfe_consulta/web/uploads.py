"""Tratamento seguro dos TXT enviados pelo navegador."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


@dataclass(frozen=True)
class UploadSummary:
    arquivos_txt: int
    arquivos_ignorados: int
    chaves: int
    bytes_recebidos: int


async def consolidar_txts(
    arquivos: list[UploadFile],
    destino: Path,
    *,
    max_bytes: int,
    max_chaves: int,
) -> UploadSummary:
    total_bytes = 0
    txts = 0
    ignorados = 0
    chaves: list[str] = []
    vistos: set[str] = set()

    for upload in arquivos:
        nome = Path(upload.filename or "").name
        if Path(nome).suffix.lower() != ".txt":
            ignorados += 1
            await upload.close()
            continue

        try:
            partes = []
            while True:
                bloco = await upload.read(min(64 * 1024, max_bytes - total_bytes + 1))
                if not bloco:
                    break
                total_bytes += len(bloco)
                if total_bytes > max_bytes:
                    raise ValueError("Os TXT enviados excedem o limite total de 2 MiB.")
                partes.append(bloco)
            bruto = b"".join(partes)
        finally:
            await upload.close()

        try:
            texto = bruto.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"TXT com codificação inválida: {nome}") from exc

        txts += 1
        for linha in texto.splitlines():
            chave = linha.strip()
            if not chave or chave in vistos:
                continue
            vistos.add(chave)
            chaves.append(chave)
            if len(chaves) > max_chaves:
                raise ValueError(f"Envio excede o limite de {max_chaves:,} chaves.")

    if txts == 0:
        raise ValueError("Selecione pelo menos um arquivo .txt.")
    if not chaves:
        raise ValueError("Nenhuma chave foi encontrada nos TXT enviados.")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(chaves) + "\n", encoding="utf-8")

    return UploadSummary(
        arquivos_txt=txts,
        arquivos_ignorados=ignorados,
        chaves=len(chaves),
        bytes_recebidos=total_bytes,
    )
