# Instalação no Windows — Consulta de Manifestação v1.0

## Requisitos

- Windows 10/11.
- Python 3.11 ou mais recente.
- `py -m pip` permitido pela TI.
- Para atualização SEFAZ: certificado A1 da empresa com chave privada em `Cert:\CurrentUser\My`.
- Acesso HTTPS ao Ambiente Nacional da NF-e.

## Instalação

Extraia o projeto para uma pasta gravável e execute:

```powershell
INSTALAR.cmd
```

Instalação manual equivalente:

```powershell
py -m pip install -e .
nfe-consulta --version
```

A versão esperada é `1.0.0`.

Para abrir:

```powershell
nfe-consulta gui
```

ou use `ABRIR_CONSULTA.cmd`.

## Atualização de versão

Preserve o banco antes de substituir a pasta do aplicativo. O banco contém o cursor NSU e o histórico local.

Após instalar uma nova versão:

```powershell
py -m pip install -e . --force-reinstall
nfe-consulta --version
```

## Desinstalação

```powershell
py -m pip uninstall nfe-consulta
```

A desinstalação do pacote não remove banco, TXT ou planilhas.

## Validação pela TI

Antes de liberar em produção:

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

Também devem ser validados certificado, proxy, acesso ao endpoint, permissões das pastas e coexistência com outros sistemas que consultam o mesmo CNPJ.
