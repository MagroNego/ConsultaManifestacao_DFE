"""Configuração central da aplicação."""

from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Consulta de Manifestação"
EMPRESA = "YAB"
CNPJ_PADRAO = "16840128000101"
UF_PADRAO = "RJ"
NOME_PLANILHA = "Consulta_Manifestacao_YAB.xlsx"
NOME_BANCO = "nfe_manifestacoes.db"
NOME_BANCO_SEGURO = "nfe_manifestacoes_seguro.db"


@dataclass(frozen=True)
class CaminhosApp:
    raiz: Path
    chaves: Path
    banco: Path
    saida: Path


def resolver_caminhos(
    raiz: Path | None = None,
    downloads: Path | None = None,
) -> CaminhosApp:
    """Resolve arquivos padrão sem misturar pastas de projeto e Downloads."""
    raiz = (raiz or Path(__file__).resolve().parent.parent).resolve()
    downloads = downloads or (Path.home() / "Downloads")

    entrada_projeto = raiz / "entrada" / "CHAVES.txt"
    banco_seguro_projeto = raiz / "dados" / NOME_BANCO_SEGURO
    banco_projeto = raiz / "dados" / NOME_BANCO

    projeto_em_uso = entrada_projeto.exists() or banco_seguro_projeto.exists() or banco_projeto.exists()
    banco_seguro_downloads = downloads / NOME_BANCO_SEGURO
    banco_downloads = downloads / NOME_BANCO
    chaves_downloads = downloads / "CHAVES.txt"
    downloads_em_uso = chaves_downloads.exists() or banco_seguro_downloads.exists() or banco_downloads.exists()

    if projeto_em_uso or not downloads_em_uso:
        chaves = entrada_projeto
        banco = banco_seguro_projeto if banco_seguro_projeto.exists() else banco_projeto
    else:
        chaves = chaves_downloads
        banco = banco_seguro_downloads if banco_seguro_downloads.exists() else banco_downloads

    # A saída pertence ao aplicativo, mesmo quando o histórico legado ainda está
    # em Downloads. Isso evita espalhar novos arquivos pelo perfil do usuário.
    saida = raiz / "saidas" / NOME_PLANILHA
    return CaminhosApp(raiz=raiz, chaves=chaves, banco=banco, saida=saida)

