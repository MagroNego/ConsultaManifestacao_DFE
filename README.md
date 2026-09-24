# nfe-consulta — Evento manifestação NFs emitidas



**Interface gráfica:** no PowerShell, `nfe-consulta --gui`, ou dê duplo clique em `ABRIR_CONSULTA.cmd`. A tela mostra o status local, os arquivos e os resultados. Escolha o TXT e o banco; a ação padrão gera Excel usando somente o banco local. A atualização remota exige escolher o botão da SEFAZ. Para o assistente antigo em texto, use `ABRIR_CONSULTA_TEXTO.cmd`.

Consulta os eventos de manifestação dos destinatários pelo serviço **NFeDistribuicaoDFe**, usando o certificado A1 já instalado no Windows. Lê um TXT com uma chave de 44 dígitos por linha e gera um CSV com a manifestação mais recente e o histórico. A sincronização busca eventos pelo `distNSU` do CNPJ emitente; **não faz uma requisição por chave**.

## Requisitos

- Windows 10/11 e Python 3.11 ou mais recente.
- Certificado do CNPJ com chave privada em `Cert:\CurrentUser\My` e acesso HTTPS ao Ambiente Nacional da NF-e.
- CNPJ do emitente e sua UF. Para certificado em outro repositório, o app precisa ser adaptado.

## Instalação

Abra o PowerShell nesta pasta (que contém `pyproject.toml`):

```powershell
py -m pip install -e . --force-reinstall
nfe-consulta --version
```

## Uso

Crie `CHAVES.txt` com uma chave por linha. No PowerShell:

```powershell
nfe-consulta --manifestacoes `
  --cnpj 16840128000101 --uf RJ `
  --lote "$HOME\Downloads\CHAVES.txt" `
  --csv "$HOME\Downloads\resultado.csv" `
  --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

Para gerar uma planilha Excel com chave como texto, número da NF-e, série, filtros e histórico legível, use `--xlsx`. Se o banco já foi sincronizado, **não precisa consultar a SEFAZ novamente**:

```powershell
nfe-consulta --cnpj 16840128000101 `
  --lote "$HOME\Downloads\CHAVES.txt" `
  --xlsx "$HOME\Downloads\resultado_formatado.xlsx" `
  --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

O número e a série são extraídos da chave de 44 dígitos. Ambos também aparecem no CSV. É possível informar `--csv` e `--xlsx` juntos para gerar os dois formatos.

É possível usar `--consultar-sefaz` ou `--sincronizar` no lugar de `--manifestacoes`, para compatibilidade de comando. As três opções **agora sincronizam por NSU**. O app seleciona automaticamente o certificado correspondente ao `--cnpj`. Se houver mais de um certificado compatível, informe `--cert-indice N` após conferir a lista exibida. `--max-lotes 50` limita a quantidade de lotes nesta execução; se ela não terminar, execute novamente para continuar. A primeira sincronização pode levar vários lotes de até 50 documentos.

Para consultar apenas o banco local, sem acessar a SEFAZ:

```powershell
nfe-consulta --cnpj 16840128000101 --lote "$HOME\Downloads\CHAVES.txt" `
  --csv "$HOME\Downloads\resultado.csv" --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

Para uma única chave use o mesmo comando com a chave como argumento posicional e sem `--lote`/`--csv`/`--xlsx`. O CSV contém `;` e UTF-8 BOM; ao abri-lo diretamente, o Excel pode converter a chave longa em número e perder dígitos. Use a planilha `.xlsx` para preservar a chave. Mantenha o mesmo arquivo de banco entre execuções.

## Interpretação do resultado

Para ver a última sincronização registrada sem chamar a SEFAZ: `nfe-consulta --status --cnpj 16840128000101 --banco "$HOME\Downloads\nfe_manifestacoes.db"`. A mesma consulta está na opção `3` do assistente. O status informa a hora da última resposta salva e se o cursor chegou ao máximo conhecido, mas não detecta novos eventos posteriores sem uma nova consulta remota.

- **Sem manifestação localizada no histórico local** significa apenas que o app não encontrou evento no período disponibilizado e sincronizado; não comprova que o destinatário nunca manifestou.
- No CSV, a coluna `cobertura` distingue histórico local, sincronização concluída e sincronização parcial. Se aparecer parcial, repita o comando para avançar o NSU antes de tirar conclusões.
- Se a primeira consulta começar de NSU zero, só eventos ainda disponibilizados pela SEFAZ poderão ser recuperados. O histórico anterior não pode ser reconstruído por esse serviço. Continue sincronizando periodicamente.
- O programa não consulta a situação da NF-e (autorização/cancelamento) e não usa `NFeConsultaProtocolo` como complemento de manifestação: conforme o MOC, a consulta de situação retorna apenas os eventos de cancelamento, carta de correção e EPEC.
- Se outra aplicação consultar o mesmo CNPJ, podem ocorrer limites compartilhados ou bloqueios `656`. Ao atingir o fim dos NSUs ou receber `137`, o programa espera pelo menos uma hora antes de nova consulta; após `656`, registra também a pausa no banco local. Não faça consultas repetidas fora do programa durante o bloqueio.

## Teste local

```powershell
py -m pip install -e ".[dev]"
py -m pytest -q
```

Os testes não fazem consulta real à SEFAZ. Validar o certificado, a conectividade e o retorno de produção requer rodar no Windows com o certificado.

Referências técnicas: [MOC 7.0, seções 5.4 e 5.7](https://www.confaz.fazenda.gov.br/legislacao/arquivo-manuais/moc7-visao-geral.pdf) e [NT 2014.002, Distribuição de DF-e](https://www.nfe.fazenda.gov.br/POrtal/exibirArquivo.aspx?conteudo=wLVBlKchUb4%3D).
