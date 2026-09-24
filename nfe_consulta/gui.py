"""Interface gráfica da Consulta de Manifestação v1."""

from __future__ import annotations

import os
import queue
import re
import sqlite3
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from openpyxl import load_workbook

from nfe_consulta import __version__
from nfe_consulta.config import (
    CNPJ_PADRAO,
    NOME_PLANILHA,
    UF_PADRAO,
    resolver_caminhos,
)
from nfe_consulta.seguranca_banco import criptografado
from nfe_consulta.servico import ParametrosConsulta, ResultadoExecucao, executar_consulta
from nfe_consulta.status import consultar_status
from nfe_consulta.validacao import numero_e_serie
from nfe_consulta.xlsx_writer import DESCRICOES


FUNDO = "#F3F5F8"
PAINEL = "#FFFFFF"
TEXTO = "#17202A"
SECUNDARIO = "#667085"
BORDA = "#E4E7EC"
PRIMARIA = "#243B53"
PRIMARIA_HOVER = "#1B2F44"
SUAVE = "#EEF2F6"
SUCESSO = "#147D64"
ALERTA = "#B54708"
ERRO = "#B42318"


def caminhos_iniciais(pasta: Path, downloads: Path) -> tuple[Path, Path, Path]:
    caminhos = resolver_caminhos(pasta, downloads)
    return caminhos.chaves, caminhos.banco, caminhos.saida


def montar_comando(
    chaves: Path,
    banco: Path,
    saida: Path,
    sincronizar: bool,
    max_lotes: int = 50,
) -> list[str]:
    """Compatibilidade para integrações da v0.9.4; a GUI v1 não usa subprocesso."""
    comando = [
        sys.executable,
        "-u",
        "-m",
        "nfe_consulta.cli",
        "--cnpj",
        CNPJ_PADRAO,
        "--lote",
        str(chaves),
        "--xlsx",
        str(saida),
        "--banco",
        str(banco),
    ]
    if sincronizar:
        if not 1 <= max_lotes <= 500:
            raise ValueError("Lotes por execução devem estar entre 1 e 500")
        comando += ["--manifestacoes", "--uf", UF_PADRAO, "--max-lotes", str(max_lotes)]
    return comando


def ler_previa(caminho: Path) -> tuple[list[tuple[str, ...]], str]:
    arquivo = load_workbook(caminho, read_only=True, data_only=True)
    try:
        aba = arquivo.active
        resumo = str(aba["A2"].value or "")
        linhas: list[tuple[str, ...]] = []
        for chave, numero, serie, evento, data, protocolo, _, _, historico, erro in aba.iter_rows(
            min_row=5, min_col=1, max_col=10, values_only=True
        ):
            if chave is not None:
                linhas.append(
                    tuple(
                        str(valor) if valor is not None else ""
                        for valor in (
                            chave,
                            numero,
                            serie,
                            evento,
                            data,
                            protocolo,
                            historico,
                            erro,
                        )
                    )
                )
        return linhas, resumo
    finally:
        arquivo.close()


def resumir_status(texto: str) -> tuple[str, str, str, str]:
    nsus = re.search(r"ultNSU salvo: (\d+) \| maxNSU conhecido: (\d+)", texto)
    resposta = re.search(
        r"Ultima resposta da SEFAZ salva: (\d{2}/\d{2}/\d{4} \d{2}:\d{2})",
        texto,
    )
    if "Não foi possível" in texto or "nao encontrado" in texto.lower():
        condicao = "Banco indisponível"
    elif "Pausa por" in texto:
        condicao = "Em pausa"
    elif "Sincronizacao parcial" in texto:
        condicao = "Parcial"
    elif nsus:
        condicao = "Sincronizado"
    else:
        condicao = "Sem histórico"
    return (
        resposta.group(1) if resposta else "Sem registro",
        nsus.group(1) if nsus else "—",
        nsus.group(2) if nsus else "—",
        condicao,
    )


def _data_exibicao(valor: str) -> str:
    if not valor:
        return ""
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return valor


class AplicativoManifestacoes(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.pasta = Path(__file__).resolve().parent.parent
        chaves, banco, saida = caminhos_iniciais(self.pasta, Path.home() / "Downloads")

        self.chaves = tk.StringVar(value=str(chaves))
        self.banco = tk.StringVar(value=str(banco))
        self.saida = tk.StringVar(value=str(saida))
        self.max_lotes = tk.StringVar(value="50")
        self.pesquisa = tk.StringVar()
        self.situacao = tk.StringVar(value="Pronto")
        self.resumo = tk.StringVar(value="Nenhum resultado nesta sessão")
        self.status_resposta = tk.StringVar(value="Sem registro")
        self.status_nsu = tk.StringVar(value="—")
        self.status_condicao = tk.StringVar(value="Sem histórico")

        self.fila: queue.Queue = queue.Queue()
        self.executando = False
        self.linhas: list[tuple[str, ...]] = []
        self._linhas_visiveis: list[tuple[str, ...]] = []
        self._senha_banco: str | None = None
        self._caminho_senha: str | None = None
        self.filtro_agendado: str | None = None
        self.ultimo_arquivo: Path | None = None
        self._log_linhas: list[str] = []

        self.title("Consulta de Manifestação")
        self.geometry("1240x760")
        self.minsize(1040, 660)
        self.configure(bg=FUNDO)

        self._configurar_estilo()
        self._montar()
        self._atualizar_status()
        self.after(100, self._processar_fila)
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure(
            "Consulta.Treeview",
            background=PAINEL,
            foreground=TEXTO,
            fieldbackground=PAINEL,
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Consulta.Treeview.Heading",
            background=SUAVE,
            foreground=SECUNDARIO,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 9, "bold"),
            padding=(8, 10),
        )
        estilo.map(
            "Consulta.Treeview",
            background=[("selected", "#E6EDF4")],
            foreground=[("selected", TEXTO)],
        )
        estilo.configure(
            "Consulta.Horizontal.TProgressbar",
            troughcolor="#E8ECF1",
            background=PRIMARIA,
            borderwidth=0,
        )

    def _label(
        self,
        pai,
        texto: str = "",
        *,
        tamanho: int = 10,
        cor: str = TEXTO,
        negrito: bool = False,
        fundo: str = PAINEL,
        **kwargs,
    ) -> tk.Label:
        return tk.Label(
            pai,
            text=texto,
            bg=fundo,
            fg=cor,
            font=("Segoe UI", tamanho, "bold" if negrito else "normal"),
            **kwargs,
        )

    def _botao(
        self,
        pai,
        texto: str,
        comando,
        *,
        primario: bool = False,
        compacto: bool = False,
    ) -> tk.Button:
        fundo = PRIMARIA if primario else SUAVE
        frente = "#FFFFFF" if primario else PRIMARIA
        ativo = PRIMARIA_HOVER if primario else "#E2E8EF"
        return tk.Button(
            pai,
            text=texto,
            command=comando,
            bg=fundo,
            fg=frente,
            activebackground=ativo,
            activeforeground=frente,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=10 if compacto else 16,
            pady=6 if compacto else 10,
        )

    def _montar(self) -> None:
        cabecalho = tk.Frame(self, bg=PAINEL, height=66, highlightbackground=BORDA, highlightthickness=1)
        cabecalho.pack(fill="x")
        cabecalho.pack_propagate(False)

        bloco_titulo = tk.Frame(cabecalho, bg=PAINEL)
        bloco_titulo.pack(side="left", padx=24)
        self._label(bloco_titulo, "Consulta de Manifestação", tamanho=18, negrito=True).pack(anchor="w")
        self._label(bloco_titulo, f"NF-e · YAB · v{__version__}", tamanho=9, cor=SECUNDARIO).pack(anchor="w")

        self.status_chip = self._label(
            cabecalho,
            textvariable=self.status_condicao,
            tamanho=9,
            cor=PRIMARIA,
            negrito=True,
            fundo=SUAVE,
            padx=12,
            pady=6,
        )
        self.status_chip.pack(side="right", padx=(8, 24))
        self._botao(cabecalho, "Manual", self._abrir_manual, compacto=True).pack(side="right")

        corpo = tk.Frame(self, bg=FUNDO)
        corpo.pack(fill="both", expand=True, padx=18, pady=18)
        corpo.grid_columnconfigure(1, weight=1)
        corpo.grid_rowconfigure(0, weight=1)

        lateral = tk.Frame(corpo, bg=PAINEL, width=310, highlightbackground=BORDA, highlightthickness=1)
        lateral.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        lateral.grid_propagate(False)
        lateral.grid_columnconfigure(0, weight=1)

        self._label(lateral, "Arquivos", tamanho=11, negrito=True).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        self._campo_arquivo(lateral, 1, "CHAVES.TXT", self.chaves, self._escolher_chaves)
        self._campo_arquivo(lateral, 2, "BANCO", self.banco, self._escolher_banco)
        self._campo_arquivo(lateral, 3, "PLANILHA", self.saida, self._escolher_saida)

        separador = tk.Frame(lateral, bg=BORDA, height=1)
        separador.grid(row=4, column=0, sticky="ew", padx=18, pady=16)

        acoes = tk.Frame(lateral, bg=PAINEL)
        acoes.grid(row=5, column=0, sticky="ew", padx=18)
        acoes.grid_columnconfigure(0, weight=1)
        self.botao_sefaz = self._botao(
            acoes,
            "Atualizar SEFAZ",
            lambda: self._executar(True),
            primario=True,
        )
        self.botao_sefaz.grid(row=0, column=0, sticky="ew")
        self.botao_local = self._botao(
            acoes,
            "Gerar Excel",
            lambda: self._executar(False),
        )
        self.botao_local.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        linha_lotes = tk.Frame(acoes, bg=PAINEL)
        linha_lotes.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self._label(linha_lotes, "Lotes", tamanho=9, cor=SECUNDARIO).pack(side="left")
        tk.Spinbox(
            linha_lotes,
            from_=1,
            to=500,
            textvariable=self.max_lotes,
            width=6,
            justify="center",
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
        ).pack(side="right")

        separador2 = tk.Frame(lateral, bg=BORDA, height=1)
        separador2.grid(row=6, column=0, sticky="ew", padx=18, pady=16)

        status = tk.Frame(lateral, bg=PAINEL)
        status.grid(row=7, column=0, sticky="ew", padx=18)
        self._label(status, "Banco local", tamanho=11, negrito=True).pack(anchor="w")
        self._label(status, textvariable=self.status_resposta, tamanho=9, cor=SECUNDARIO).pack(
            anchor="w", pady=(8, 0)
        )
        self._label(status, textvariable=self.status_nsu, tamanho=9, cor=TEXTO, negrito=True).pack(
            anchor="w", pady=(3, 0)
        )
        self._botao(status, "Recarregar", self._atualizar_status, compacto=True).pack(
            anchor="w", pady=(10, 0)
        )

        lateral.grid_rowconfigure(8, weight=1)
        rodape_lateral = tk.Frame(lateral, bg=PAINEL)
        rodape_lateral.grid(row=9, column=0, sticky="sew", padx=18, pady=18)
        self._botao(rodape_lateral, "Logs", self._abrir_logs, compacto=True).pack(side="left")
        self._label(
            rodape_lateral,
            textvariable=self.situacao,
            tamanho=9,
            cor=SECUNDARIO,
        ).pack(side="right")

        principal = tk.Frame(corpo, bg=PAINEL, highlightbackground=BORDA, highlightthickness=1)
        principal.grid(row=0, column=1, sticky="nsew")
        principal.grid_columnconfigure(0, weight=1)
        principal.grid_rowconfigure(1, weight=1)

        topo = tk.Frame(principal, bg=PAINEL)
        topo.grid(row=0, column=0, sticky="ew", padx=18, pady=14)
        self._label(topo, "Resultados", tamanho=12, negrito=True).pack(side="left")
        self._label(topo, textvariable=self.resumo, tamanho=9, cor=SECUNDARIO).pack(
            side="left", padx=(12, 0)
        )
        self._botao(topo, "Abrir Excel", self._abrir_excel, compacto=True).pack(side="right")

        busca = tk.Entry(
            topo,
            textvariable=self.pesquisa,
            width=28,
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
        )
        busca.pack(side="right", padx=(0, 10), ipady=6)
        busca.insert(0, "")
        self.pesquisa.trace_add("write", self._agendar_filtro)

        tabela_frame = tk.Frame(principal, bg=PAINEL)
        tabela_frame.grid(row=1, column=0, sticky="nsew", padx=18)
        tabela_frame.grid_columnconfigure(0, weight=1)
        tabela_frame.grid_rowconfigure(0, weight=1)

        colunas = ("numero", "serie", "evento", "data", "chave")
        self.arvore = ttk.Treeview(
            tabela_frame,
            columns=colunas,
            show="headings",
            style="Consulta.Treeview",
            selectmode="browse",
        )
        configuracao = (
            ("numero", "NOTA", 90, False),
            ("serie", "SÉRIE", 70, False),
            ("evento", "MANIFESTAÇÃO", 230, True),
            ("data", "DATA", 145, False),
            ("chave", "CHAVE DE ACESSO", 360, True),
        )
        for chave, titulo, largura, esticar in configuracao:
            self.arvore.heading(chave, text=titulo)
            self.arvore.column(chave, width=largura, minwidth=60, stretch=esticar)
        self.arvore.grid(row=0, column=0, sticky="nsew")
        self.arvore.bind("<<TreeviewSelect>>", self._detalhes_selecao)

        scroll_y = ttk.Scrollbar(tabela_frame, orient="vertical", command=self.arvore.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        self.arvore.configure(yscrollcommand=scroll_y.set)
        self.arvore.tag_configure("alternada", background="#FAFBFC")

        detalhes = tk.Frame(principal, bg=SUAVE)
        detalhes.grid(row=2, column=0, sticky="ew", padx=18, pady=14)
        self.detalhes = self._label(
            detalhes,
            "Selecione uma nota para ver o histórico.",
            tamanho=9,
            cor=SECUNDARIO,
            fundo=SUAVE,
            anchor="w",
            justify="left",
            wraplength=820,
            padx=12,
            pady=10,
        )
        self.detalhes.pack(fill="x")

        progresso_frame = tk.Frame(principal, bg=PAINEL)
        progresso_frame.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.progresso = ttk.Progressbar(
            progresso_frame,
            mode="determinate",
            maximum=100,
            style="Consulta.Horizontal.TProgressbar",
        )
        self.progresso.pack(fill="x")

    def _campo_arquivo(
        self,
        pai,
        linha: int,
        titulo: str,
        variavel: tk.StringVar,
        selecionar,
    ) -> None:
        bloco = tk.Frame(pai, bg=PAINEL)
        bloco.grid(row=linha, column=0, sticky="ew", padx=18, pady=5)
        bloco.grid_columnconfigure(0, weight=1)
        self._label(bloco, titulo, tamanho=8, cor=SECUNDARIO, negrito=True).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        entrada = tk.Entry(
            bloco,
            textvariable=variavel,
            font=("Segoe UI", 9),
            fg=TEXTO,
            bg="#FBFCFD",
            relief="solid",
            borderwidth=1,
        )
        entrada.grid(row=1, column=0, sticky="ew", ipady=6)
        self._botao(bloco, "…", selecionar, compacto=True).grid(row=1, column=1, padx=(6, 0))

    def _escolher_chaves(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Chaves",
            initialdir=str(Path(self.chaves.get()).expanduser().parent),
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if caminho:
            self.chaves.set(caminho)

    def _escolher_banco(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Banco",
            initialdir=str(Path(self.banco.get()).expanduser().parent),
            filetypes=[("Banco SQLite", "*.db"), ("Todos", "*.*")],
        )
        if caminho:
            self.banco.set(caminho)
            self._senha_banco = None
            self._caminho_senha = None
            self._atualizar_status()

    def _escolher_saida(self) -> None:
        caminho = filedialog.asksaveasfilename(
            parent=self,
            title="Planilha",
            initialdir=str(Path(self.saida.get()).expanduser().parent),
            initialfile=NOME_PLANILHA,
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if caminho:
            self.saida.set(caminho)

    def _senha_para_banco(self) -> str | None:
        caminho = self.banco.get().strip().strip('"')
        if not criptografado(caminho):
            return None
        if self._caminho_senha != caminho or not self._senha_banco:
            senha = simpledialog.askstring(
                "Banco protegido",
                "Senha",
                show="*",
                parent=self,
            )
            if not senha:
                return None
            self._senha_banco = senha
            self._caminho_senha = caminho
        return self._senha_banco

    def _atualizar_status(self) -> None:
        try:
            senha = self._senha_para_banco()
            if criptografado(self.banco.get()) and not senha:
                return
            texto = consultar_status(self.banco.get(), CNPJ_PADRAO, senha=senha)
        except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
            if "Senha incorreta" in str(exc):
                self._senha_banco = None
            texto = f"Não foi possível ler o banco: {exc}"

        resposta, ult_nsu, max_nsu, condicao = resumir_status(texto)
        self.status_resposta.set(resposta)
        self.status_nsu.set(f"NSU {ult_nsu} / {max_nsu}")
        self.status_condicao.set(condicao)

    def _executar(self, sincronizar: bool) -> None:
        if self.executando:
            return

        chaves = Path(self.chaves.get().strip().strip('"')).expanduser()
        banco = Path(self.banco.get().strip().strip('"')).expanduser()
        saida = Path(self.saida.get().strip().strip('"')).expanduser()

        if not chaves.is_file():
            messagebox.showerror("Arquivo não encontrado", str(chaves), parent=self)
            return
        if saida.suffix.lower() != ".xlsx":
            messagebox.showerror("Planilha inválida", "Use um arquivo .xlsx.", parent=self)
            return
        if not sincronizar and not banco.is_file():
            messagebox.showerror("Banco não encontrado", str(banco), parent=self)
            return

        try:
            max_lotes = int(self.max_lotes.get())
            if not 1 <= max_lotes <= 500:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lotes inválidos", "Use um valor entre 1 e 500.", parent=self)
            return

        if sincronizar and not banco.exists():
            if not messagebox.askyesno(
                "Novo banco",
                "Criar um novo banco de sincronização?",
                parent=self,
            ):
                return

        try:
            senha = self._senha_para_banco()
            if criptografado(banco) and not senha:
                return
        except OSError as exc:
            messagebox.showerror("Banco indisponível", str(exc), parent=self)
            return

        parametros = ParametrosConsulta(
            chaves=chaves,
            banco=banco,
            saida=saida,
            cnpj=CNPJ_PADRAO,
            uf=UF_PADRAO,
            sincronizar_sefaz=sincronizar,
            max_lotes=max_lotes,
            senha_banco=senha,
        )

        self.executando = True
        self.botao_local.configure(state="disabled")
        self.botao_sefaz.configure(state="disabled")
        self.progresso.configure(value=0)
        self.situacao.set("SEFAZ" if sincronizar else "Processando")
        self._log_linhas.clear()
        self._registrar("Atualização SEFAZ" if sincronizar else "Consulta local")

        threading.Thread(
            target=self._trabalhar,
            args=(parametros,),
            daemon=True,
        ).start()

    def _trabalhar(self, parametros: ParametrosConsulta) -> None:
        try:
            resultado = executar_consulta(
                parametros,
                progresso_sincronizacao=lambda lote, ult, maximo, novos: self.fila.put(
                    ("log", f"Lote {lote} · NSU {ult}/{maximo} · +{novos} evento(s)")
                ),
                progresso_lote=lambda atual, total: self.fila.put(
                    ("progresso", atual, total)
                ),
            )
            self.fila.put(("fim", resultado))
        except Exception as exc:
            self.fila.put(("falha", str(exc)))

    def _processar_fila(self) -> None:
        try:
            while True:
                evento = self.fila.get_nowait()
                tipo = evento[0]
                if tipo == "log":
                    self._registrar(evento[1])
                elif tipo == "progresso":
                    atual, total = evento[1], evento[2]
                    self.progresso.configure(value=(atual / max(1, total)) * 100)
                elif tipo == "fim":
                    self._finalizar()
                    self._aplicar_resultado(evento[1])
                    self._atualizar_status()
                elif tipo == "falha":
                    self._finalizar()
                    self._registrar(f"Erro: {evento[1]}")
                    self.situacao.set("Falha")
                    messagebox.showerror("Consulta não concluída", evento[1], parent=self)
                    self._atualizar_status()
        except queue.Empty:
            pass
        self.after(100, self._processar_fila)

    def _aplicar_resultado(self, execucao: ResultadoExecucao) -> None:
        linhas: list[tuple[str, ...]] = []
        for resultado in execucao.resultados:
            numero, serie = numero_e_serie(resultado.chave)
            evento = resultado.manifestacoes[-1] if resultado.manifestacoes else None
            descricao = (
                DESCRICOES.get(evento.codigo, evento.descricao)
                if evento
                else "Sem evento localizado"
            )
            historico = "\n".join(
                f"{_data_exibicao(item.data)} · "
                f"{DESCRICOES.get(item.codigo, item.descricao)} · {item.protocolo}"
                for item in resultado.manifestacoes
            )
            linhas.append(
                (
                    resultado.chave,
                    numero or "",
                    serie or "",
                    descricao,
                    _data_exibicao(evento.data) if evento else "",
                    evento.protocolo if evento else "",
                    historico,
                    resultado.erro or "",
                )
            )

        self.linhas = linhas
        self.ultimo_arquivo = execucao.saida
        self.resumo.set(
            f"{execucao.total} notas · {execucao.com_evento} com manifestação"
        )
        self.situacao.set("Concluído")
        self.progresso.configure(value=100)
        self._mostrar_linhas()

    def _finalizar(self) -> None:
        self.executando = False
        self.botao_local.configure(state="normal")
        self.botao_sefaz.configure(state="normal")

    def _agendar_filtro(self, *_args) -> None:
        if self.filtro_agendado:
            self.after_cancel(self.filtro_agendado)
        self.filtro_agendado = self.after(160, self._mostrar_linhas)

    def _mostrar_linhas(self) -> None:
        self.filtro_agendado = None
        self.arvore.delete(*self.arvore.get_children())
        termo = self.pesquisa.get().strip().lower()
        visiveis = [
            linha
            for linha in self.linhas
            if not termo
            or termo in linha[0].lower()
            or termo in linha[1].lower()
            or termo in linha[3].lower()
        ]
        self._linhas_visiveis = visiveis[:1000]

        for indice, linha in enumerate(self._linhas_visiveis):
            chave, numero, serie, evento, data, _, _, erro = linha
            self.arvore.insert(
                "",
                "end",
                iid=str(indice),
                values=(numero, serie, erro or evento, data, chave),
                tags=("alternada",) if indice % 2 else (),
            )
        self.detalhes.configure(text="Selecione uma nota para ver o histórico.")

    def _detalhes_selecao(self, _evento=None) -> None:
        selecao = self.arvore.selection()
        if not selecao:
            return
        linha = self._linhas_visiveis[int(selecao[0])]
        historico, erro = linha[6], linha[7]
        self.detalhes.configure(
            text=erro or historico or "Nenhum evento localizado no histórico."
        )

    def _registrar(self, texto: str) -> None:
        self._log_linhas.append(texto)

    def _abrir_logs(self) -> None:
        janela = tk.Toplevel(self)
        janela.title("Logs")
        janela.geometry("760x360")
        janela.configure(bg=PAINEL)
        texto = tk.Text(
            janela,
            bg="#101828",
            fg="#F2F4F7",
            insertbackground="#FFFFFF",
            relief="flat",
            font=("Cascadia Mono", 9),
            wrap="word",
            padx=12,
            pady=12,
        )
        texto.pack(fill="both", expand=True)
        texto.insert("1.0", "\n".join(self._log_linhas) or "Sem logs nesta sessão.")
        texto.configure(state="disabled")

    def _abrir_manual(self) -> None:
        caminho = self.pasta / "MANUAL_DE_USO.md"
        if not caminho.is_file():
            messagebox.showinfo("Manual", str(caminho), parent=self)
            return
        try:
            os.startfile(str(caminho))
        except (AttributeError, OSError):
            messagebox.showinfo("Manual", str(caminho), parent=self)

    def _abrir_excel(self) -> None:
        caminho = self.ultimo_arquivo or Path(self.saida.get()).expanduser()
        if not caminho.is_file():
            messagebox.showinfo("Planilha", "Nenhuma planilha disponível.", parent=self)
            return
        try:
            os.startfile(str(caminho))
        except (AttributeError, OSError):
            messagebox.showinfo("Planilha", str(caminho), parent=self)

    def _fechar(self) -> None:
        if self.executando:
            messagebox.showinfo(
                "Consulta em andamento",
                "Finalize a consulta antes de fechar.",
                parent=self,
            )
            return
        self.destroy()


def main() -> None:
    app = AplicativoManifestacoes()
    app.mainloop()


if __name__ == "__main__":
    main()
