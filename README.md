# Consulta de Manifestação — v1.0

Aplicativo Windows para consultar eventos de manifestação de NF-e pelo **NFeDistribuicaoDFe**, manter o histórico em SQLite/SQLCipher e gerar uma planilha Excel.

## Interface gráfica

Depois da instalação:

```powershell
nfe-consulta gui
```

Ou dê duplo clique em `ABRIR_CONSULTA.cmd`.

A tela v1 usa o mesmo núcleo da CLI. A interface não abre outro processo do terminal para executar a consulta.

## CLI

Os comandos principais são:

```powershell
nfe-consulta atualizar
nfe-consulta excel
nfe-consulta status
nfe-consulta gui
```

- `atualizar`: sincroniza o histórico com a SEFAZ e gera o Excel.
- `excel`: gera o Excel usando somente o banco local.
- `status`: mostra o estado da última sincronização gravada no banco.
- `gui`: abre a interface gráfica.

Os caminhos padrão são resolvidos nas pastas `entrada`, `dados` e `saidas`. Também é possível informar os arquivos explicitamente:

```powershell
nfe-consulta atualizar entrada\CHAVES.txt `
  --banco dados\nfe_manifestacoes_seguro.db `
  --saida saidas\Consulta_Manifestacao_YAB.xlsx `
  --max-lotes 50
```

Consulta local:

```powershell
nfe-consulta excel entrada\CHAVES.txt `
  --banco dados\nfe_manifestacoes_seguro.db `
  --saida saidas\Consulta_Manifestacao_YAB.xlsx
```

## Instalação

Requisitos:

- Windows 10/11.
- Python 3.11 ou mais recente.
- Certificado A1 da empresa instalado no repositório do usuário do Windows.
- Acesso ao Ambiente Nacional da NF-e.

Na pasta do projeto:

```powershell
py -m pip install -e .
nfe-consulta --version
```

Ou execute `INSTALAR.cmd`.

## Estrutura

```text
entrada/     CHAVES.txt
dados/       banco SQLite ou SQLCipher
saidas/      planilhas geradas
nfe_consulta/
  servico.py       fluxo compartilhado pela GUI e CLI
  distribuicao.py  comunicação NFeDistribuicaoDFe
  banco.py         persistência e controle de NSU
  gui.py           interface
  cli.py           terminal
```

## Controle de consumo

O cursor NSU é persistido no banco. Quando a SEFAZ retorna rejeição **656 — Consumo Indevido**, o aplicativo grava uma pausa preventiva antes de permitir nova sincronização. Uma sincronização completa recente também é reaproveitada para evitar consultas desnecessárias.

O histórico disponível depende do que o Ambiente Nacional ainda disponibiliza para distribuição. A ausência de evento no banco local não prova que nunca houve manifestação.

## Banco protegido

Para criar uma cópia SQLCipher:

```powershell
nfe-consulta proteger-banco dados\nfe_manifestacoes.db dados\nfe_manifestacoes_seguro.db
```

O banco de origem é preservado.

## Testes

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

Os testes automatizados não fazem consulta real à SEFAZ.
