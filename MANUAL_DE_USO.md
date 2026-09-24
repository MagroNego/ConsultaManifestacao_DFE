# Como consultar manifestações

Veja [SEGURANCA_BANCO.md](SEGURANCA_BANCO.md) para migrar o banco atual com senha e abri-lo no DB Browser.

## Interface gráfica (recomendado)

1. Após instalar a versão 0.9.4, execute `nfe-consulta --gui` no PowerShell ou dê duplo clique em `ABRIR_CONSULTA.cmd`.
2. Confira os caminhos do TXT, banco `nfe_manifestacoes.db` e planilha. A interface dá prioridade ao banco protegido em `dados/`, depois ao banco protegido em Downloads.
3. Clique em **Gerar planilha com banco local** para atualizar o Excel sem acessar a SEFAZ. A faixa superior mostra a última resposta e os NSUs. Clique em **Ver status completo** para ver horário de espera e motivo de uma pausa `656`, se houver.
4. Depois que a pausa terminar e a TI confirmar a rotina do mesmo CNPJ, clique em **Atualizar na SEFAZ + gerar planilha** para buscar eventos novos. A interface pede confirmação antes de iniciar uma chamada remota.
5. Use a busca da tabela para achar uma nota ou chave, clique em uma linha para ver o histórico e em **Abrir Excel** para abrir a planilha completa. A tabela exibe até 1.000 linhas por vez; a planilha contém todo o resultado.

O botão **Mostrar detalhes** exibe os lotes, o certificado selecionado e o `xMotivo` de possíveis erros. Feche o Excel antes de gerar novamente a planilha. O comando `nfe-consulta --gui` não consulta a SEFAZ apenas por abrir a janela.

## Assistente em texto

1. Crie `entrada/CHAVES.txt` com **uma chave de NF-e de 44 dígitos por linha**. Pode deixar o TXT em Downloads e escolher o caminho quando o assistente perguntar.
2. Dê duplo clique em `ABRIR_CONSULTA_TEXTO.cmd`.
3. Escolha `1` para atualizar os eventos na SEFAZ e gerar a planilha. Escolha `2` para gerar uma planilha apenas com o banco local, sem chamada à SEFAZ. Escolha `3` para verificar o status local do banco (não precisa de TXT nem de certificado).
4. Pressione Enter para aceitar os caminhos sugeridos ou digite outros caminhos. O assistente dá preferência ao banco protegido em `dados/`, depois ao banco protegido em Downloads.
5. Abra `saidas/Consulta_Manifestacao_YAB.xlsx`. Se ela estiver aberta no Excel durante uma nova geração, feche o arquivo e execute novamente a opção `2`.

A primeira atualização pode levar muitos lotes. O limite do assistente é 500 lotes por execução; se aparecer **sincronização parcial**, execute novamente a opção `1` com o mesmo banco. Quando `ultNSU = maxNSU`, os lotes disponíveis foram percorridos. Consultas posteriores usam o cursor salvo. Ao chegar ao fim, o programa observa intervalo mínimo de uma hora antes de pedir novos dados.

## Como saber quando o banco foi atualizado

Escolha `3` no assistente. Ele mostra a data e hora local da **última resposta da SEFAZ salva no banco**, `ultNSU`, `maxNSU` e se existe uma pausa por `656`. Não faz consulta remota nem modifica o banco. `ultNSU = maxNSU` significa que a fila conhecida naquela resposta foi percorrida; **não comprova que nenhum evento novo chegou depois**. Se a última consulta terminou há menos de uma hora, aguarde o horário informado. Após esse horário, escolha `1` para verificar novidades. Se `ultNSU < maxNSU`, a sincronização está parcial: execute `1` com o mesmo banco para continuar. Gerar Excel pela opção `2` não atualiza a data de consulta.

Nas rejeições `656` recebidas **a partir da versão 0.6.3**, o programa mostra o `xMotivo` devolvido pela SEFAZ e o mantém no status local, mesmo depois da pausa. Uma rejeição anterior não pode ser recuperada do banco se só foi registrada com a mensagem genérica. Não faça uma consulta antecipada apenas para obter o motivo: respeite a pausa e verifique com a TI se outra aplicação também consulta NSUs para o mesmo CNPJ.

**Sem evento localizado** indica ausência no histórico consultado. Pode haver eventos fora do período disponibilizado ou ainda não recebidos. **Ciência da Operação** é preliminar; uma manifestação conclusiva pode aparecer depois.

## Atalho no PowerShell

Para usar a pasta do projeto, feche o aplicativo e o DB Browser; coloque `CHAVES.txt` em `entrada/` e **mova** `nfe_manifestacoes_seguro.db` para `dados/` na pasta que contém `INSTALAR.cmd`. O resultado vai para `saidas/`. Se deixar os dois arquivos em Downloads, os atalhos continuam usando Downloads. Se apenas um arquivo estiver no projeto, o atalho para e informa qual falta, sem misturar caminhos. Confira os caminhos exibidos antes dos lotes.


Com o TXT e o banco protegido na pasta do projeto ou ambos em Downloads, execute apenas:

```powershell
nfe-consulta --atualizar
```

O atalho usa o CNPJ e a UF configurados para a YAB, atualiza os NSUs na SEFAZ e grava `Consulta_Manifestacao_YAB.xlsx` em `saidas/` quando usa o projeto, ou em Downloads quando usa Downloads. Ele solicita a senha do banco. Se faltar o TXT ou o banco protegido, interrompe sem consultar a SEFAZ e sem criar outro banco. Confira os caminhos que aparecem no terminal antes dos lotes. Feche a planilha no Excel antes de executar.

Para atualizar **somente a planilha**, sem certificado e sem consultar a SEFAZ, execute:

```powershell
nfe-consulta --excel
```

Esse comando lê o mesmo banco protegido e TXT escolhidos pelo atalho, pede a senha e sobrescreve a planilha em `saidas/` ou em Downloads, conforme os caminhos usados. Feche a planilha no Excel antes de executá-lo.

## Linha de comando

Ajuda: `nfe-consulta --help` ou `nfe-consulta -help`.

Interface gráfica: `nfe-consulta --gui`.

Ver status sem consultar a SEFAZ, no PowerShell:

```powershell
nfe-consulta --status --cnpj 16840128000101 `
  --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

Atualizar e exportar, no PowerShell:

```powershell
nfe-consulta --manifestacoes --cnpj 16840128000101 --uf RJ `
  --lote ".\entrada\CHAVES.txt" `
  --xlsx ".\saidas\Consulta_Manifestacao_YAB.xlsx" `
  --banco ".\dados\nfe_manifestacoes.db" --max-lotes 500
```

Somente gerar Excel com banco já preenchido:

```powershell
nfe-consulta --cnpj 16840128000101 `
  --lote "$HOME\Downloads\CHAVES.txt" `
  --xlsx "$HOME\Downloads\Consulta_Manifestacao_YAB.xlsx" `
  --banco "$HOME\Downloads\nfe_manifestacoes.db"
```

Para CSV, use `--csv caminho.csv`; é possível usar CSV e XLSX juntos. Ao abrir CSV diretamente no Excel, a chave de 44 dígitos pode ser convertida em número. Use o `.xlsx` para preservar todos os dígitos. O número e a série da nota são extraídos da chave.

## Se algo falhar

- `403`: confira o certificado escolhido. O aplicativo procura o mesmo CNPJ; em caso de ambiguidade, use `--cert-indice` após conferir a lista.
- `656`: consumo indevido; não repita a consulta durante uma hora. O programa mantém uma pausa local no banco.
- Arquivo em uso: feche a planilha no Excel e escolha `2` para gerá-la outra vez.
- Se o banco for novo, o histórico anterior ao período disponível no Ambiente Nacional pode não ser recuperável.

Não envie o banco, chaves ou planilhas a terceiros sem seguir as regras internas de compartilhamento de dados da empresa.

A planilha XLSX começa com título e contagem de chaves; o cabeçalho da tabela fica na linha 4 e os resultados começam na linha 5. Os detalhes de cobertura continuam disponíveis no status e nas mensagens do terminal.
