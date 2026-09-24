# Instalação no Windows — Consulta de manifestação YAB

## Requisitos

- Windows 10/11, Python 3.11 ou superior e `py -m pip` habilitado pela TI.
- Para a sincronização: certificado A1 da empresa com chave privada no repositório `Cert:\CurrentUser\My` da conta que executará o programa; acesso HTTPS ao Ambiente Nacional da NF-e.
- Para gerar apenas o Excel a partir de um banco existente, a conexão com a SEFAZ e o certificado não são necessários.

## Instalar

1. Extraia o ZIP para uma pasta **gravável pelo usuário**. Não execute de dentro do ZIP; mantenha a pasta após a instalação, pois o pacote usa instalação editável.
2. dê duplo clique em `INSTALAR.cmd`. O arquivo apenas chama `py -m pip install -e .`; ele não solicita administrador nem altera a política de execução do PowerShell. A instalação pode baixar `openpyxl`, `defusedxml` e `sqlcipher3`.
3. Confirme no terminal: `nfe-consulta --version` deve mostrar `0.9.4`.

Para abrir a interface gráfica: `nfe-consulta --gui` ou duplo clique em `ABRIR_CONSULTA.cmd`. A biblioteca `tkinter` faz parte da instalação usual do Python para Windows. O assistente anterior continua em `ABRIR_CONSULTA_TEXTO.cmd`.

Instalação manual equivalente no PowerShell, **dentro da pasta extraída**:

```powershell
py -m pip install -e .
py -m nfe_consulta.cli --version
```

Se o ambiente corporativo usar repositório interno ou instalação offline.
## Preservar o histórico já sincronizado

O arquivo `nfe_manifestacoes.db` contém o último NSU e os eventos obtidos. Se você já o tem em Downloads, o assistente o seleciona automaticamente. **Não apague nem reinicie o banco antigo.** A atualização do programa não exige repetir os lotes anteriores.

Use a opção `3` do assistente para ver a última resposta da SEFAZ armazenada. Essa leitura não altera o banco e não exige certificado. Para buscar eventos surgidos depois, use a opção `1` quando passar o intervalo indicado.

Para manter o banco protegido na pasta do programa, feche o aplicativo e o DB Browser e mova `nfe_manifestacoes_seguro.db` para `dados/nfe_manifestacoes_seguro.db`; mova `CHAVES.txt` para `entrada/CHAVES.txt`. A planilha será gerada em `saidas/` pelos atalhos. Confira o NSU e faça backup antes de mover; use sempre a mesma cópia ativa do banco para não separar o histórico de NSUs. Mantenha a pasta extraída, pois a instalação é editável.

## Atualizar ou desinstalar

- Atualizar: instale uma nova versão aprovada pela TI na pasta desejada e execute `py -m pip install -e .`. Preserve o banco separadamente e selecione o caminho no assistente.
- Desinstalar o pacote Python: `py -m pip uninstall nfe-consulta`. O banco e as planilhas locais não são removidos automaticamente.

Consulte [MANUAL_DE_USO.md](MANUAL_DE_USO.md) para operação e [REVISAO.md](REVISAO.md) para avaliação de segurança.

## Criptografia do banco

Consulte [SEGURANCA_BANCO.md](SEGURANCA_BANCO.md). A migração é explícita e cria outro arquivo; o original não é apagado. O banco criptografado pede senha no CLI, na interface e no DB Browser com suporte a SQLCipher.
